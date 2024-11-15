# app/plugins/image_generator/models.py

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union
import eqty
import re
from app.models.query import QueryRequest
from dataclasses import dataclass


class ImageMetadata(BaseModel):
    src: str = Field(..., description="The URL to the image.")
    description: str = Field(..., description="A description of the image.")


class ImageGeneratorQueryRequest(QueryRequest):
    selected_images: Optional[Dict[str, ImageMetadata]] = Field(
        default=None,
        alias="selectedImages",
        description="A dictionary of selected images to be used for image generation, keyed by unique image IDs.",
    )


class ApiframeResponse(BaseModel):
    status: str
    task_id: str
    task_type: str
    sref: Optional[str] = None
    percentage: Optional[Union[str, int]] = None
    original_image_url: Optional[str] = None
    image_urls: Optional[List[str]] = None
    manifest_url: Optional[str] = None

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
