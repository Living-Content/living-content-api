# plugins/audio_generator/functions.py

import json
import logging
from datetime import UTC, datetime

import eqty

# Local Plugin Imports
from providers.jenai.jenai_request_handler import (
    JenaiRequestHandler,
)

from app.lib import save_asset
from app.models.query import Messages, QueryRequest


class AudioGeneratorFunctions:
    def __init__(self, function_handler):
        self.function_handler = function_handler
        self.config = function_handler.config
        self.secrets = function_handler.secrets
        self.notification_manager = function_handler.notification_manager
        self.content_session_manager = function_handler.content_session_manager
        self.logger = logging.getLogger(__name__)
        self.jenai_request_handler = JenaiRequestHandler(self.config, self.secrets)

    async def generate_a_song_prompt(
        self,
        user_query: QueryRequest,
        user_id: eqty.Asset,
        content_session_id: str,
        request_message_id: eqty.Asset = None,
        response_message_id: eqty.Asset = None,
        generated_data: eqty.Asset | None = None,
        media_asset: eqty.CID | None = None,
    ):
        # Prepare query messages
        system_prompt = user_query.system_prompt
        response_schema = user_query.response_schema
        additional_data = user_query.additional_data

        user_query.messages = [{"role": "user", "content": additional_data}]
        user_query.messages.insert(0, Messages(role="system", content=system_prompt))
        model = user_query.model or self.config.get("clients", {}).get(
            "openai", {}
        ).get("model")

        # Send request to OpenAI API
        response = (
            await self.function_handler.openai_client.client.chat.completions.create(
                model=model,
                messages=user_query.messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": response_schema,
                },
                max_tokens=int(self.config["clients"]["openai"]["max_tokens"]),
                stream=False,
            )
        )

        # Process and log the response
        llm_response = response.choices[0].message.content.strip()
        self.logger.debug(f"LLM raw response: {llm_response}")

        if not llm_response:
            raise ValueError("Received empty response from LLM")

        try:
            # Parse the response as JSON
            result = json.loads(llm_response)
            self.logger.debug(f"Parsed LLM response: {result}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding JSON: {e!s}")

        return result

    async def generate_a_song(
        self,
        user_query: QueryRequest,
        user_id: eqty.Asset,
        content_session_id: str,
        request_message_id: eqty.Asset = None,
        response_message_id: eqty.Asset = None,
        generated_data: eqty.Asset | None = None,
        media_asset: eqty.CID | None = None,
    ):

        additional_data = user_query.additional_data

        logging.info(f"Additional Data: {additional_data}")

        endpoint = "/api/v1/public/track/generate"

        request_message = (
            user_query.messages[-1].content
            if user_query.messages
            else "No message content"
        )

        if generated_data is not None:
            prompt = generated_data.strip()
        elif additional_data is not None:
            prompt = additional_data
        else:
            prompt = request_message

        data = self.jenai_request_handler.create_jenai_payload(prompt)

        response = await self.jenai_request_handler.post_jenai_request(endpoint, data)

        task_id = response["data"][0].get("id") if response.get("data") else None

        response_toast = "Your request to generate a song has been received."

        response_message = f"# Your request to generate a song has been received.\n\nYou will be notified when the song is ready.\n\nTogether, we came up with the following prompt:\n\n**{prompt}**"

        notification_data = {
            "toast_message": response_toast,
            "toast_type": "text",
            "persistent": False,
        }
        await self.notification_manager.create_notification(
            user_id.value, content_session_id, notification_data
        )

        task_asset = {
            task_id: {
                "prompt": prompt,
                "createdAt": datetime.now(UTC).isoformat(),
                "status": "processing",
                "endpoint": endpoint,
            }
        }

        # Update content session directly
        new_data = {
            "query": {
                "queries": [
                    {
                        "messageId": request_message_id.value,
                        "createdAt": datetime.now(UTC).isoformat(),
                        "role": "user",
                        "content": request_message,
                    },
                    {
                        "messageId": response_message_id.value,
                        "createdAt": datetime.now(UTC).isoformat(),
                        "role": "assistant",
                        "content": response_message,
                    },
                ]
            },
            "plugins": {"AudioGenerator": task_asset},
        }

        logging.info(f"Updating content session with data: {new_data}")
        logging.info(f"Content Session ID: {content_session_id}")
        logging.info(f"User ID: {user_id.value}")
        await self.content_session_manager.update_content_session(
            user_id.value, content_session_id, new_data
        )

        result = eqty.Asset(
            json.dumps(
                {"message": response_message, "task_id": task_id, "prompt": prompt}
            ),
            name="API response",
            data_type="Data",
            blob_type=eqty.sdk.metadata.BlobType.FILE,
            asset_type=eqty.sdk.asset.AssetType.DOCUMENT,
            description="Response message from API",
            project=content_session_id,
        )
        save_asset(result)

        return (result, task_asset)
