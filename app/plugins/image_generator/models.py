# app/plugins/image_generator/models.py

import re
from dataclasses import dataclass

import eqty
from pydantic import BaseModel, Field

from app.models.query import QueryRequest


class ImageMetadata(BaseModel):
    src: str = Field(..., description="The URL to the image.")
    description: str = Field(..., description="A description of the image.")


class ImageGeneratorQueryRequest(QueryRequest):
    selected_images: dict[str, ImageMetadata] | None = Field(
        default=None,
        alias="selectedImages",
        description="A dictionary of selected images to be used for image generation, keyed by unique image IDs.",
    )


class ApiframeResponse(BaseModel):
    status: str
    task_id: str
    task_type: str
    sref: str | None = None
    percentage: str | int | None = None
    original_image_url: str | None = None
    image_urls: list[str] | None = None
    manifest_url: str | None = None

    @property
    def is_final(self) -> bool:
        return self.status == "finished" and self.image_urls is not None

    def to_eqty_asset(self, content_session_id: str):
        asset = eqty.Asset(
            self,
            name="APIFRAME result",
            data_type="Data",
            blob_type=eqty.sdk.metadata.BlobType.FILE,
            asset_type=eqty.sdk.asset.AssetType.DOCUMENT,
            description="Asynchronous result from APIFRAME used to generate images",
            project=content_session_id,
        )
        return asset

    def serialize_for_hashing(self):
        return self.model_dump_json(by_alias=True).encode("utf-8")


class ApiframeRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "1:1"
    process_mode: str = "fast"
    webhook_url: str
    webhook_secret: str


@dataclass
class TaskData:
    task_id: str
    created_at: str
    user_id: str
    content_session_id: str
    request_message_id: str
    response_message_id: str
    prompt: str
    aspect_ratio: str
    webhook_secret: str

    def to_json(self):
        return {
            "taskId": self.task_id,
            "createdAt": self.created_at,
            "userId": self.user_id,
            "contentSessionId": self.content_session_id,
            "requestMessageId": self.request_message_id,
            "responseMessageId": self.response_message_id,
            "prompt": self.prompt,
            "aspectRatio": self.aspect_ratio,
            "webhookSecret": self.webhook_secret,
        }

    def to_eqty_asset(self):
        return eqty.Asset(
            self,
            name="Context data",
            data_type="Data",
            blob_type=eqty.sdk.metadata.BlobType.FILE,
            asset_type=eqty.sdk.asset.AssetType.DOCUMENT,
            description="Contextual data for asynchronous response handling",
            project=self.content_session_id,
        )

    @staticmethod
    def from_json(json):
        snake_case_data = {
            TaskData.camel_to_snake(key): value for key, value in json.items()
        }
        return TaskData(**snake_case_data)

    @staticmethod
    def camel_to_snake(camel_str):
        return re.sub(r"(?<!^)(?=[A-Z])", "_", camel_str).lower()
