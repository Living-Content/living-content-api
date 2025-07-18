import json
import logging
import os
import shutil
import uuid
from datetime import UTC, datetime

import aiohttp
import boto3
import eqty
from fastapi import HTTPException

from app.lib import save_asset
from app.lib.dependencies import get_config, get_secrets

# Local Plugin Imports
from app.plugins.image_generator.models import ApiframeResponse, TaskData


class ApiframeResponseHandler:
    def __init__(self, content_session_manager, notification_manager):
        self._logger = logging.getLogger(__name__)
        self.content_session_manager = content_session_manager
        self.notification_manager = notification_manager
        self.redis_ops = content_session_manager.redis_ops

    async def store_initial_task_data(self, task_data: TaskData):
        redis_key = f"apiframeTask:{task_data.task_id}"
        await self.redis_ops.redis_client.set(
            redis_key, json.dumps(task_data.to_json()), ex=3600
        )

    def construct_response_message(self, prompt, image_url):
        return f"# We've received your request and are working on it.\n\n*You don't need to stay on this page; you'll have a notification waiting when it's done.\n\nTogether, we came up with the following prompt:\n\n**{prompt}**\n\nThis is the image we're using:\n\n![Source Image]({image_url}){{.no-remix.living-content-image-embedded}}"

    async def process_apiframe_response(
        self, response: ApiframeResponse, stored_data: TaskData
    ):
        try:
            if response.is_final:
                response_asset = response.to_eqty_asset(stored_data.content_session_id)

                download_task = eqty.Compute(
                    self.download_generated_images,
                    metadata={
                        "name": "Run download_generated_images",
                        "project": stored_data.content_session_id,
                        "description": "Computation to download and hash the generated images",
                    },
                )
                save_asset(download_task._code_asset)
                await download_task(response_asset, stored_data)

                url = self.generate_and_upload_manifest(stored_data.content_session_id)
                response.manifest_url = url

                return await self._handle_final_response(response, stored_data)
            else:
                await self._handle_interim_response(response, stored_data)
                return {
                    "status": "interim_response",
                    "percentage": response.percentage,
                }

        except Exception as e:
            self._logger.error(
                f"Error processing Apiframe response for task {response.task_id}: {e!s}"
            )
            raise HTTPException(
                status_code=500, detail="Error processing Apiframe response"
            )

    async def get_stored_task_data(self, task_id: str) -> TaskData:
        redis_key = f"apiframeTask:{task_id}"
        stored_data = await self.redis_ops.redis_client.get(redis_key)
        if not stored_data:
            raise HTTPException(
                status_code=404, detail="No stored data found for this task"
            )

        stored_data = json.loads(stored_data)
        if not stored_data.get("userId") or not stored_data.get("contentSessionId"):
            raise HTTPException(
                status_code=400, detail="Missing required data in stored task"
            )

        task_data = TaskData.from_json(stored_data)

        return task_data

    async def _handle_interim_response(
        self, response: ApiframeResponse, task_data: TaskData
    ):
        self._logger.info(
            f"Processing interim response for task {response.task_id}. Status: {response.status}, Progress: {response.percentage}%"
        )

        percentage = response.percentage

        toast_message = f"{percentage}"

        if response.percentage is not None:
            notification_data = {
                "associated_task_id": response.task_id,
                "associated_image": response.sref,
                "toast_message": toast_message,
                "toast_type": "progress",
                "response_data": response.model_dump_json(),
                "persistent": True,
            }
            await self.notification_manager.create_notification(
                task_data.user_id, task_data.content_session_id, notification_data
            )

        await self.redis_ops.redis_client.set(
            f"apiframeTask:{response.task_id}",
            json.dumps(task_data.to_json()),
            ex=3600,
        )

    async def _handle_final_response(
        self, response: ApiframeResponse, task_data: TaskData
    ):
        self._logger.info(f"Processing final response for task {response.task_id}")
        apiframe_task_id = f"apiframeTask:{response.task_id}"
        message_id = str(uuid.uuid4())

        if not response.image_urls:
            associated_message = "No images were found in the response."
        elif len(response.image_urls) == 1:
            associated_message = (
                f"# Your new image has been created.\n\n"
                f"[![Generated Image]({response.image_urls[0]}){{.living-content-image.living-content-image-embedded}}]({response.image_urls[0]}){{.living-content-image-link}}\n\n"
                f"View your [Lineage Explorer]({response.manifest_url}){{.living-content-lineage-explorer-link}} to see the resulting graph."
            )
        else:
            associated_message = (
                "# Your new images have been created.\n\n"
                + "".join(
                    f"[![Generated Image]({url}){{.living-content-image.living-content-image-embedded}}]({url}){{.living-content-image-embedded-link}}\n"
                    for url in response.image_urls
                )
                + "\n\nView your "
                + f"[Lineage Explorer]({response.manifest_url}){{.living-content-lineage-explorer-link}} to see the result graph."
            )

        new_data = {
            "plugins": {
                "ImageGenerator": {
                    apiframe_task_id: {
                        "createdAt": datetime.now(UTC).isoformat(),
                        "messageId": message_id,
                        "taskId": response.task_id,
                        "sref": response.sref,
                        "originalImageUrl": response.original_image_url,
                        "generatedImageUrls": response.image_urls,
                        "prompt": task_data.prompt,
                        "aspectRatio": task_data.aspect_ratio,
                        "status": response.status,
                    }
                }
            },
            "query": {
                "queries": [
                    {
                        "messageId": message_id,
                        "createdAt": datetime.now(UTC).isoformat(),
                        "role": "assistant",
                        "content": associated_message,
                    }
                ]
            },
        }

        await self.content_session_manager.update_content_session(
            task_data.user_id, task_data.content_session_id, new_data
        )

        progress_notification_data = {
            "associated_task_id": response.task_id,
            "associated_image": response.sref,
            "toast_message": "100",
            "toast_type": "progress",
            "response_data": response.model_dump_json(),
            "persistent": False,
        }
        await self.notification_manager.create_notification(
            task_data.user_id, task_data.content_session_id, progress_notification_data
        )

        final_image_notification_data = {
            "associated_message_id": message_id,
            "associated_message": associated_message,
            "toast_type": "silent",
            "response_data": response.model_dump_json(),
            "persistent": False,
        }
        await self.notification_manager.create_notification(
            task_data.user_id,
            task_data.content_session_id,
            final_image_notification_data,
        )

        await self.redis_ops.redis_client.delete(f"apiframeTask:{response.task_id}")

    # EQTY SDK code

    async def download_generated_images(
        self, response: eqty.Asset, stored_data: TaskData
    ):
        """
        Code for downloading of generated images.
        """
        if response.image_urls is None:
            raise ValueError("No image URLs found in Apiframe response")

        image_datasets: list[eqty.Asset] = []

        id = 1

        async with aiohttp.ClientSession() as session:
            for image_url in response.image_urls:
                async with session.get(image_url) as resp:
                    if resp.status != 200:
                        raise ValueError(f"Failed to download image from {image_url}")

                    image_data = await resp.read()

                cid = eqty.get_cid_for_bytes(image_data)

                # Save the image to disk
                config = eqty.sdk.config.Config()
                session_dir = os.path.join(
                    config.config_dir, stored_data.content_session_id, "assets"
                )
                os.makedirs(session_dir, exist_ok=True)
                image_filename = os.path.join(session_dir, cid)
                with open(image_filename, "wb") as image_file:
                    image_file.write(image_data)

                dataset = eqty.CID(
                    cid,
                    project=stored_data.content_session_id,
                    name=f"Generated image #{id}",
                    description="Image generated from approved function and asset pair",
                    skip_registration=False,
                    blob_type=eqty.sdk.metadata.BlobType.FILE,
                    asset_type=eqty.sdk.asset.AssetType.DOCUMENT,
                )
                image_datasets.append(dataset)
                id = id + 1

        return tuple(image_datasets)

    def generate_and_upload_manifest(self, content_session_id: str) -> str | None:
        session_dir = os.path.join(
            eqty.sdk.config.Config().config_dir, content_session_id
        )
        assets_dir = os.path.join(session_dir, "assets")
        manifest_file = os.path.join(assets_dir, "manifest.json")

        eqty.generate_manifest(manifest_file, content_session_id)

        config = get_config()
        secrets = get_secrets()

        aws_credentials = {
            "aws_access_key_id": secrets["aws_access_key_id"],
            "aws_secret_access_key": secrets["aws_secret_access_key"],
        }

        eqty_config = config["eqty"]

        # Define the required AWS configuration keys
        required_keys = ["aws_s3_bucket", "aws_region", "lineage_explorer_url"]

        # Find any missing or empty required keys
        missing_or_empty_keys = [
            key for key in required_keys if not eqty_config.get(key)
        ]

        if missing_or_empty_keys:
            self._logger.warning(
                f"AWS configuration missing or empty required keys: {', '.join(missing_or_empty_keys)}. "
                "Manifest will not be uploaded."
            )
            return None

        # If all keys are present and valid, proceed to use them
        aws_s3_bucket = eqty_config["aws_s3_bucket"]
        aws_region = eqty_config["aws_region"]
        lineage_explorer_url = eqty_config["lineage_explorer_url"]

        # Proceed with uploading to S3
        self.upload_directory_to_s3(
            assets_dir, aws_s3_bucket, content_session_id, aws_credentials
        )

        return f"{lineage_explorer_url}?manifest_url=https://s3.{aws_region}.amazonaws.com/{aws_s3_bucket}/{content_session_id}/manifest.json"

    # uploads all files in the directory to S3 then deletes the directory
    def upload_directory_to_s3(
        self,
        directory_path: str,
        bucket_name: str,
        s3_base_path: str,
        aws_credentials: dict,
    ):
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_credentials["aws_access_key_id"],
            aws_secret_access_key=aws_credentials["aws_secret_access_key"],
        )

        for root, dirs, files in os.walk(directory_path):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                s3_key = os.path.join(
                    s3_base_path, os.path.relpath(file_path, directory_path)
                )

                s3_client.upload_file(
                    file_path, bucket_name, s3_key, ExtraArgs={"ACL": "public-read"}
                )

        shutil.rmtree(directory_path)
