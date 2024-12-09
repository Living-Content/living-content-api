# app/plugins/speech_services/providers/openai/realtime_client.py

import json
import logging
from typing import Dict, Any
from enum import Enum


class EventType(Enum):
    RESPONSE_CREATE = "response.create"
    CONVERSATION_ITEM_CREATE = "conversation.item.create"
    SESSION_UPDATE = "session.update"
    AUDIO_BUFFER_APPEND = "input_audio_buffer.append"
    AUDIO_BUFFER_COMMIT = "input_audio_buffer.commit"


class OpenAiRealtimeClient:
    """
    Protocol handler for OpenAI's real-time API.
    Focuses on message formatting and protocol, not connection management.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-realtime-preview-2024-10-01"):
        self.api_key = api_key
        self.model = model
        self.logger = logging.getLogger(__name__)

    def get_connection_details(self) -> Dict[str, Any]:
        """Get WebSocket connection details"""
        return {
            "url": f"wss://api.openai.com/v1/realtime?model={self.model}",
            "headers": {
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1",
            },
        }

    def create_session_config(self, voice: str = "alloy") -> str:
        """Create session configuration message"""
        config = {
            "type": EventType.SESSION_UPDATE.value,
            "session": {
                "voice": voice,
                "turn_detection": {
                    "mode": "server",
                },
            },
        }
        return json.dumps(config)

    def create_text_message(self, text: str) -> str:
        """Create text input message"""
        message = {
            "type": EventType.CONVERSATION_ITEM_CREATE.value,
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            },
        }
        return json.dumps(message)

    def create_response_request(self) -> str:
        """Create response request message"""
        return json.dumps(
            {
                "type": EventType.RESPONSE_CREATE.value,
                "response": {"modalities": ["text", "audio"]},
            }
        )

    def create_audio_message(self, audio_chunk: bytes) -> str:
        """Create audio chunk message"""
        message = {
            "type": EventType.AUDIO_BUFFER_APPEND.value,
            "input_audio": {"format": "wav", "chunk": audio_chunk},
        }
        return json.dumps(message)

    def create_audio_commit(self) -> str:
        """Create audio commit message"""
        return json.dumps({"type": EventType.AUDIO_BUFFER_COMMIT.value})

    def parse_message(self, message: bytes | str) -> Dict[str, Any]:
        """Parse received message"""
        if isinstance(message, bytes):
            return {"type": "audio", "data": message}

        try:
            return json.loads(message)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse message: {message}")
            return {"type": "error", "message": "Failed to parse server message"}
