# app/plugins/audio_generator/jenai_request_handler.py

import logging
from app.plugins.audio_generator.jenai_client import Jenai_Client


class JenaiRequestHandler:
    _instance = None

    def __new__(cls, config, secrets):
        if cls._instance is None:
            cls._instance = super(JenaiRequestHandler, cls).__new__(cls)
            cls._instance.config = config
            cls._instance._logger = logging.getLogger(__name__)
            cls._instance.jenai_client = Jenai_Client(
                base_url=config["plugins"]["audio_generator"]["clients"]["jenai"].get(
                    "jenai_base_url", "https://jen-staging.futureverseai.com"
                ),
                api_key=secrets["jenai_api_key"],
            )
        return cls._instance

    def create_jenai_payload(self, prompt):
        return {
            "prompt": prompt,
            "format": "wav",
            "fadeOutLength": 0,
            "duration": 45,
            "styleFilter": "imogen-3000",
        }

    async def post_jenai_request(self, endpoint, data=None):
        self._logger.info("Submitting audio generation task to JenAI")
        response = await self.jenai_client.make_request("POST", endpoint, data)
        self._logger.info(f"Response from JenAI: {response}")
        return response

    async def get_jenai_status(self, endpoint, data=None):
        self._logger.info("Requesting audio generation status from JenAI")
        response = await self.jenai_client.make_request("GET", endpoint, data)
        self._logger.info(f"Response from JenAI: {response}")
        return response
