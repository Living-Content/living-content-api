# app/plugins/image_generator/apiframe_request_handler.py

import logging
import uuid
import re

# Local Plugin Imports
from apiframe_client import Apiframe_Client


class ApiframeRequestHandler:
    _instance = None

    def __new__(cls, config, secrets):
        if cls._instance is None:
            cls._instance = super(ApiframeRequestHandler, cls).__new__(cls)
            cls._instance.config = config
            cls._instance._logger = logging.getLogger(__name__)
            cls._instance.apiframe_client = Apiframe_Client(
                base_url=config["plugins"]["image_generator"]["clients"][
                    "apiframe"
                ].get("apiframe_base_url", "https://api.apiframe.pro"),
                api_key=secrets["apiframe_api_key"],
            )
        return cls._instance

    def extract_image_info(self, selected_images):
        image_url = None
        image_description = None
        aspect_ratio = "1:1"

        if selected_images:
            first_image_key = next(iter(selected_images))
            first_image = selected_images[first_image_key]
            image_url = first_image.get("src")
            image_description = first_image.get("description")
            aspect_ratio = first_image.get("aspectRatio", "1:1")

        return image_url, image_description, aspect_ratio

    def extract_prompt(self, messages):
        if messages and isinstance(messages, list) and len(messages) > 0:
            content = messages[0].content
            # Regular expression to find URLs
            url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
            # Replace URLs with an empty string
            content_without_urls = re.sub(url_pattern, "", content)
            return content_without_urls
        return None

    def construct_midjourney_prompt(self, prompt, image_url, aspect_ratio):
        return f"{prompt} --sref {image_url} --stylize 50 --ar {aspect_ratio} --v 6.0"

    def create_apiframe_payload(self, prompt, aspect_ratio, config):
        return {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "webhook_url": f"{config['ingress']['api_host_url']}/image-generator/apiframe/response",
            "webhook_secret": str(uuid.uuid4()),
        }

    async def submit_apiframe_request(self, data):
        self._logger.info("Submitting image generation task to apiframe")
        response = await self.apiframe_client.make_request("POST", "/imagine", data)
        self._logger.info(f"Response from Apiframe: {response}")
        return response
