# app/plugins/speech_services/handlers/realtime_handler.py

from typing import Dict, Any
import logging
from fastapi import Depends
from app.clients.websocket_client import WebSocketClient
from app.lib.dependencies import get_websocket_client, get_websocket_manager
from app.lib.websocket_manager import WebSocketManager


class RealtimeHandler:
    """
    Handles speech services using the main application's WebSocket infrastructure
    """

    def __init__(
        self,
        websocket_manager: WebSocketManager = Depends(get_websocket_manager),
        websocket_client: WebSocketClient = Depends(get_websocket_client),
    ):
        self.websocket_manager = websocket_manager
        self.websocket_client = websocket_client
        self.logger = logging.getLogger(__name__)
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    async def handle_speech_start(
        self, user_id: str, client_id: str, data: Dict[str, Any]
    ):
        """Handle start of speech session"""
        session_id = f"speech_{user_id}_{client_id}"

        # Initialize OpenAI session configuration
        config_message = {
            "type": "session.update",
            "session": {
                "voice": data.get("voice", "alloy"),
                "turn_detection": {"mode": "server"},
            },
        }

        # Store session info
        self.active_sessions[session_id] = {
            "user_id": user_id,
            "client_id": client_id,
            "config": data,
        }

        # Send through existing WebSocket infrastructure
        await self.websocket_client.send_message(
            user_id,
            {
                "type": "speech_session_started",
                "session_id": session_id,
                "config": config_message,
            },
        )

    async def handle_text_input(
        self, user_id: str, client_id: str, data: Dict[str, Any]
    ):
        """Handle text input for TTS"""
        message = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": data["text"]}],
            },
        }

        await self.websocket_client.send_message(user_id, message)

        # Request response with both text and audio
        await self.websocket_client.send_message(
            user_id,
            {"type": "response.create", "response": {"modalities": ["text", "audio"]}},
        )

    async def handle_audio_input(
        self, user_id: str, client_id: str, audio_chunk: bytes
    ):
        """Handle audio input for STT"""
        message = {
            "type": "input_audio_buffer.append",
            "input_audio": {
                "format": "wav",  # Adjust based on your audio format
                "chunk": audio_chunk,
            },
        }

        await self.websocket_client.send_message(user_id, message)

    async def handle_speech_end(
        self, user_id: str, client_id: str, data: Dict[str, Any]
    ):
        """Handle end of speech session"""
        session_id = f"speech_{user_id}_{client_id}"

        if session_id in self.active_sessions:
            # Cleanup session
            session_info = self.active_sessions.pop(session_id)

            # Notify client
            await self.websocket_client.send_message(
                user_id, {"type": "speech_session_ended", "session_id": session_id}
            )


# Register the handlers with your WebSocket manager
def init_speech_handlers(
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
):
    realtime_handler = RealtimeHandler(websocket_manager)

    # Register message handlers
    handlers = {
        "speech_start": realtime_handler.handle_speech_start,
        "speech_text_input": realtime_handler.handle_text_input,
        "speech_audio_input": realtime_handler.handle_audio_input,
        "speech_end": realtime_handler.handle_speech_end,
    }

    for message_type, handler in handlers.items():
        websocket_manager.register_message_handler(message_type, handler)
