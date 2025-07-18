# app/plugins/image_generator/functions.py

import json
import logging
import os
import shutil
import uuid
from datetime import UTC, datetime

import aiohttp
import eqty
from eqty.sdk.core import add_data_statement
from fastapi import HTTPException

# Local Plugin Imports
from models import TaskData
from providers.apiframe.apiframe_request_handler import ApiframeRequestHandler
from providers.apiframe.apiframe_response_handler import (
    ApiframeResponseHandler,
)

from app.lib import save_asset
from app.models.query import QueryRequest


class ImageGeneratorFunctions:
    def __init__(self, function_handler):
        self.function_handler = function_handler
        self.config = function_handler.config
        self.secrets = function_handler.secrets
        self._logger = logging.getLogger(__name__)
        self.content_session_manager = function_handler.content_session_manager
        self.notification_manager = function_handler.notification_manager
        self.redis_ops = self.content_session_manager.redis_ops
        self.apiframe_request_handler = ApiframeRequestHandler(
            self.config, self.secrets
        )
        self.apiframe_response_handler = ApiframeResponseHandler(
            self.content_session_manager, self.notification_manager
        )

    async def download_asset(
        self,
        user_query: QueryRequest,
        function_id: str,
        content_session_id: str,
    ):
        """
        Code for downloading of approved asset
        """
        selected_images = (
            user_query.plugin_data.get("selectedImages")
            if user_query.plugin_data
            else None
        )
        image_url, _, _ = self.apiframe_request_handler.extract_image_info(
            selected_images
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    raise ValueError(f"Failed to download image from {image_url}")

                image_data = await response.read()

        cid = eqty.get_cid_for_bytes(image_data)

        # Save the image to disk
        config = eqty.sdk.config.Config()
        session_dir = os.path.join(config.config_dir, content_session_id)
        assets_dir = os.path.join(session_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)
        image_filename = os.path.join(assets_dir, cid)
        with open(image_filename, "wb") as image_file:
            image_file.write(image_data)

        # copy in pre-signed statement for the corresponding asset
        signed_statement_dir = os.path.join(
            self.config["eqty"]["pre_signed_statement_dir"], cid
        )

        if signed_statement_dir and os.path.exists(signed_statement_dir):
            for item in os.listdir(signed_statement_dir):
                s = os.path.join(signed_statement_dir, item)
                d = os.path.join(session_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
        else:
            self._logger.warning(
                f"Pre-signed statements directory '{signed_statement_dir}' not found. Creating unsigned data statement"
            )
            add_data_statement([cid], True, content_session_id)

        # return a dataset for graph lineage
        return eqty.CID(cid)

    async def describe_an_image(
        self,
        user_query: QueryRequest,
        eqty_user_id: eqty.Asset,
        content_session_id: str,
        eqty_request_message_id: eqty.Asset,
        eqty_response_message_id: eqty.Asset,
        generated_data: eqty.Asset | None = None,
        image_asset: eqty.CID | None = None,
    ):
        selected_images = (
            user_query.plugin_data.get("selectedImages")
            if user_query.plugin_data
            else None
        )
        image_url, image_description, _ = (
            self.apiframe_request_handler.extract_image_info(selected_images)
        )

        if not image_url:
            return self._error_response(
                "You need to select an image.",
                eqty_user_id.value,
                content_session_id,
            )

        if not image_description:
            prompt = generated_data.strip()

            response_message = (
                self.apiframe_response_handler.construct_response_message(
                    prompt, image_url
                )
            )

        task_id = uuid.uuid4()

        task_data = TaskData(
            task_id,
            eqty_user_id.value,
            content_session_id,
            eqty_request_message_id.value,
            eqty_response_message_id.value,
            prompt,
        )

        result = eqty.Asset(
            json.dumps({"message": response_message, "task_id": task_id}),
            name="API response",
            data_type="Data",
            blob_type=eqty.sdk.metadata.BlobType.FILE,
            asset_type=eqty.sdk.asset.AssetType.DOCUMENT,
            description="Response message from API",
            project=content_session_id,
        )
        save_asset(result)

        task_asset = task_data.to_eqty_asset()
        save_asset(task_asset)

        return (result, task_asset)

    async def generate_an_image(
        self,
        user_query: QueryRequest,
        eqty_user_id: eqty.Asset,
        content_session_id: str,
        request_message_id: eqty.Asset,
        response_message_id: eqty.Asset,
        generated_data: eqty.Asset | None = None,
        plugin_data: eqty.Asset | None = None,
        image_asset: eqty.CID | None = None,
    ):
        request_message = (
            user_query.messages[-1].content
            if user_query.messages
            else "No message content"
        )
        selected_images = (
            user_query.plugin_data.get("selectedImages")
            if user_query.plugin_data
            else None
        )

        try:
            image_url, image_description, aspect_ratio = (
                self.apiframe_request_handler.extract_image_info(selected_images)
            )
            prompt = self.apiframe_request_handler.extract_prompt(user_query.messages)

            if not (prompt and image_url):
                return self._error_response(
                    "You need to provide a prompt and select an image to generate a new image.",
                    eqty_user_id.value,
                    content_session_id,
                )

            if generated_data and generated_data.value is not None:
                prompt = generated_data.value.strip()

            full_prompt = self.apiframe_request_handler.construct_midjourney_prompt(
                prompt, image_url, aspect_ratio
            )

            payload = self.apiframe_request_handler.create_apiframe_payload(
                full_prompt, aspect_ratio, self.config
            )

            response = await self.apiframe_request_handler.submit_apiframe_request(
                payload
            )
            task_id = response.get("task_id")

            if not task_id:
                raise ValueError("No task_id in apiframe response")

            created_at = datetime.now(UTC).isoformat()

            task_data = TaskData(
                task_id,
                created_at,
                eqty_user_id.value,
                content_session_id,
                request_message_id.value,
                response_message_id.value,
                prompt,
                aspect_ratio,
                payload["webhook_secret"],
            )

            await self.apiframe_response_handler.store_initial_task_data(task_data)

            response_message = (
                self.apiframe_response_handler.construct_response_message(
                    prompt, image_url
                )
            )

            notification_data = {
                "toast_message": "Your image generation request has been received.",
                "toast_type": "text",
                "persistent": False,
            }
            await self.notification_manager.create_notification(
                task_data.user_id, task_data.content_session_id, notification_data
            )

            # Update content session directly
            new_data = {
                "query": {
                    "queries": [
                        {
                            "messageId": request_message_id.value,
                            "createdAt": created_at,
                            "role": "user",
                            "content": request_message,
                        },
                        {
                            "messageId": response_message_id.value,
                            "createdAt": created_at,
                            "role": "assistant",
                            "content": response_message,
                        },
                    ]
                },
            }
            await self.content_session_manager.update_content_session(
                eqty_user_id.value, content_session_id, new_data
            )

            result = eqty.Asset(
                json.dumps({"message": response_message, "task_id": task_id}),
                name="API response",
                data_type="Data",
                blob_type=eqty.sdk.metadata.BlobType.FILE,
                asset_type=eqty.sdk.asset.AssetType.DOCUMENT,
                description="Response message from API",
                project=content_session_id,
            )
            save_asset(result)

            task_asset = task_data.to_eqty_asset()
            save_asset(task_asset)

            return (result, task_asset)

        except Exception as e:
            self._logger.error(f"Error in generate_an_image: {e!s}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Error in image generation process: {e!s}"
            )

    def _error_response(self, message, user_id=None, content_session_id=None):
        if (
            user_id is not None
            and content_session_id is not None
            and self.notification_manager is not None
        ):
            notification_data = {
                "toast_message": message,
                "toast_type": "text",
                "persistent": False,
            }
            self.notification_manager.create_notification(
                user_id, content_session_id, notification_data
            )
        return {"status": "error", "message": message}
