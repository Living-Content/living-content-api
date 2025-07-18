# app/plugins/speech_services/handlers/realtime_handler.py

import logging
from collections.abc import AsyncGenerator
from typing import Any

import aiohttp
from fastapi import HTTPException

from app.lib.dependencies import (
    get_secrets,
)


class OpenAiTtsHandler:
    """
    Handles speech services using the main application's WebSocket infrastructure
    """

    def __init__(
        self,
    ):
        self.secrets = get_secrets()
        self.logger = logging.getLogger(__name__)
        self.active_sessions: dict[str, dict[str, Any]] = {}

    async def stream_openai_tts(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Stream audio from OpenAI's TTS endpoint
        """
        openai_api_key = self.secrets.get("openai_api_key")
        if not openai_api_key:
            self.logger.error("Missing OpenAI API key.")
            raise HTTPException(status_code=500, detail="API key not configured.")

        openai_tts_url = "https://api.openai.com/v1/audio/speech"
        headers = {
            "Authorization": f"Bearer {openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"input": text, "voice": "alloy", "format": "mp3", "model": "tts-1"}

        self.logger.info(f"Starting TTS streaming for text: {text[:50]}...")
        self.logger.debug(f"Payload: {payload}")

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                async with session.post(
                    openai_tts_url, json=payload, headers=headers
                ) as response:
                    if response.status != 200:
                        error_message = await response.text()
                        self.logger.error(f"OpenAI API Error: {error_message}")
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Error from OpenAI API: {error_message}",
                        )

                    async for chunk in response.content.iter_chunked(1024):
                        try:
                            yield chunk
                        except Exception as chunk_error:
                            self.logger.error(f"Error processing chunk: {chunk_error}")
                            raise HTTPException(
                                status_code=500, detail="Error streaming audio."
                            )
        except aiohttp.ClientError as network_error:
            self.logger.error(f"Network error during TTS request: {network_error}")
            raise HTTPException(
                status_code=500,
                detail="Network error occurred while accessing OpenAI TTS service.",
            )
        except Exception as general_error:
            self.logger.error(f"Unexpected error during TTS streaming: {general_error}")
            raise HTTPException(
                status_code=500,
                detail="An unexpected error occurred during TTS processing.",
            )
