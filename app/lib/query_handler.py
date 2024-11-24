from fastapi import HTTPException
import os
import shutil
import logging
import inspect
import json
import uuid
import filelock
from pathlib import Path
from contextlib import contextmanager
from app.lib import save_asset
from app.clients.openai_client import OpenAI_Client
from fastapi.responses import StreamingResponse, JSONResponse
import eqty


@contextmanager
def _file_lock(path: str):
    """Context manager for file locking"""
    lock = filelock.FileLock(f"{path}.lock")
    try:
        with lock:
            yield
    finally:
        if os.path.exists(f"{path}.lock"):
            try:
                os.remove(f"{path}.lock")
            except OSError:
                pass


class QueryHandler:
    def __init__(self, config, secrets, content_session_manager, function_handler):
        logging.debug("Initializing QueryHandler")
        self.config = config
        self.secrets = secrets
        self.content_session_manager = content_session_manager
        self._logger = logging.getLogger(__name__)
        self.function_handler = function_handler
        self.openai_client = OpenAI_Client(config, secrets)

    async def submit_query_request(
        self,
        eqty_user_query: eqty.Asset,
        eqty_user_id: eqty.Asset,
        content_session_id: str,
    ):
        try:
            # Check for function_id and determine if we need to select a function
            function_id = eqty_user_query.function_id
            logging.debug(f"Initial function_id: {function_id}")
            logging.debug(f"User query: {eqty_user_query}")

            # If no function_id, use select_function to determine it
            select_function_wrapper = eqty.Compute(
                self.function_handler.select_function,
                metadata={
                    "name": "Run select_function",
                    "description": "Computation to interpret user prompt and select a function using ChatGPT",
                    "project": content_session_id,
                },
            )

            with _file_lock(str(select_function_wrapper._code_asset.cid)):
                save_asset(select_function_wrapper._code_asset)

            # Pass function_id to select_function if available
            (function_id, generated_data) = await select_function_wrapper(
                eqty_user_query, content_session_id, function_id=function_id
            )

            (should_stream, selected_function_wrapper, module) = (
                await self.function_handler.load_function(
                    function_id,
                    eqty_user_query,
                )
            )

            logging.debug(f"Selected function: {selected_function_wrapper}")
            logging.debug(f"Module: {module}")

            download_asset_to_eqty_sdk = getattr(module, "download_asset", None)
            if download_asset_to_eqty_sdk is not None:
                download_function_wrapper = eqty.Compute(
                    download_asset_to_eqty_sdk,
                    metadata={
                        "name": "Run download_asset",
                        "description": "Computation to download and hash the selected asset",
                        "project": content_session_id,
                    },
                )
                with _file_lock(str(download_function_wrapper._code_asset.cid)):
                    save_asset(download_function_wrapper._code_asset)

                asset = await download_function_wrapper(
                    eqty_user_query, function_id, content_session_id
                )
            else:
                asset = None

            request_message_id = create_uuid_asset(
                "UUID",
                "Identifier for request message.",
                content_session_id,
            )
            response_message_id = create_uuid_asset(
                "UUID",
                "Identifier for response message.",
                content_session_id,
            )

            if should_stream:

                async def stream_with_flag():
                    try:
                        initial_data = {
                            "streaming": True,
                            "requestMessageId": request_message_id.value,
                            "responseMessageId": response_message_id.value,
                        }
                        yield json.dumps(initial_data)
                        function_response = selected_function_wrapper(
                            eqty_user_query,
                            eqty_user_id,
                            content_session_id,
                            request_message_id,
                            response_message_id,
                            generated_data,
                            asset,
                        )
                        async for data in function_response:
                            yield data
                    except HTTPException as http_exc:
                        yield "\n\n" + "data: An error occurred.\n\n"
                        raise http_exc
                    except Exception as e:
                        error_message = f"Unexpected error: {str(e)}"
                        self._logger.error(error_message)
                        yield "\n\n" + "data: An error occurred\n\n"
                        raise HTTPException(status_code=500, detail=error_message)
                    finally:
                        manifest_path = Path("manifest.json")
                        with _file_lock(str(manifest_path)):
                            eqty.generate_manifest(
                                str(manifest_path), content_session_id
                            )

                return StreamingResponse(
                    stream_with_flag(), media_type="text/event-stream"
                )
            else:
                # Call the function
                result = await selected_function_wrapper(
                    eqty_user_query,
                    eqty_user_id,
                    content_session_id,
                    request_message_id,
                    response_message_id,
                    generated_data,
                    asset,
                )

                if isinstance(result, tuple):
                    function_response, callback_task_data = result
                else:
                    function_response = result
                    callback_task_data = None

                logging.debug(f"Function response after execution: {function_response}")
                logging.debug(f"Callback task data: {callback_task_data}")

                with _file_lock(f"compute_{content_session_id}"):
                    code_cid = create_compute_asset_statement(
                        selected_function_wrapper, content_session_id, self.config
                    )
                    compute_cid = eqty.sdk.core.add_computation_statement(
                        inputs=[
                            getattr(eqty_user_query, "cid", "fallback_cid"),
                            getattr(eqty_user_id, "cid", "fallback_cid"),
                            getattr(request_message_id, "cid", "fallback_cid"),
                            getattr(response_message_id, "cid", "fallback_cid"),
                            getattr(generated_data, "cid", "fallback_cid"),
                            getattr(asset, "cid", "fallback_cid"),
                            code_cid,
                        ],
                        outputs=[
                            getattr(function_response, "cid", "fallback_cid"),
                            getattr(callback_task_data, "cid", "fallback_cid"),
                        ],
                        computation=None,
                        issue_vc=True,
                        project=content_session_id,
                    )

                    eqty.sdk.core.add_metadata_statement(
                        compute_cid,
                        f'{{"name": "Run {function_id}", "namespace": "PROJECT_ID", "type": "Computation", "description": "Computation to execute the selected function" }}',
                        True,
                        project=content_session_id,
                    )

                try:
                    if isinstance(function_response, dict):
                        response_content = function_response
                    elif hasattr(function_response, "value"):
                        response_content = function_response.value
                    else:
                        response_content = str(function_response)

                    parsed_value = (
                        json.loads(response_content)
                        if isinstance(response_content, str)
                        else response_content
                    )

                    return JSONResponse(
                        content={
                            "streaming": False,
                            "data": parsed_value,
                            "requestMessageId": request_message_id.value,
                            "responseMessageId": response_message_id.value,
                        },
                        media_type="application/json",
                    )
                except json.JSONDecodeError:
                    return JSONResponse(
                        content={
                            "streaming": False,
                            "data": response_content,
                            "requestMessageId": request_message_id.value,
                            "responseMessageId": response_message_id.value,
                        },
                        media_type="application/json",
                    )

        except ValueError as e:
            logging.error(f"Value Error. {e}")
            raise HTTPException(status_code=400, detail=str(e))

        except Exception as e:
            logging.error(f"General error during query request handling. {e}")
            raise HTTPException(status_code=500, detail=str(e))


def create_compute_asset_statement(
    selected_function_wrapper, content_session_id: str, config: dict
) -> str:
    source_code = inspect.getsource(selected_function_wrapper)
    func_bytes = source_code.encode("utf-8")
    cid = eqty.sdk.core.get_cid_for_bytes(func_bytes)

    signed_statement_dir = os.path.join(config["eqty"]["pre_signed_statement_dir"], cid)

    if signed_statement_dir and os.path.exists(signed_statement_dir):
        session_dir = os.path.join(
            eqty.sdk.config.Config().config_dir, content_session_id
        )

        os.makedirs(session_dir, exist_ok=True)

        with _file_lock(str(Path(session_dir) / "copy_lock")):
            for item in os.listdir(signed_statement_dir):
                s = os.path.join(signed_statement_dir, item)
                d = os.path.join(session_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
    else:
        with _file_lock(str(Path(content_session_id) / "statement_lock")):
            eqty.sdk.core.add_data_statement([cid], False, content_session_id)

    return cid


def create_uuid_asset(name: str, desc: str, content_session_id: str) -> eqty.Asset:
    id = str(uuid.uuid4())
    id_asset = eqty.Asset(
        id,
        name=name,
        data_type="Data",
        blob_type=eqty.sdk.metadata.BlobType.FILE,
        asset_type=eqty.sdk.asset.AssetType.DOCUMENT,
        description=desc,
        project=content_session_id,
    )
    logging.debug(f"UUID Asset Created: {id_asset}")

    with _file_lock(str(id_asset.cid)):
        save_asset(id_asset)

    return id_asset
