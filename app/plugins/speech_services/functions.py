import logging
from typing import Dict, Any
from app.models.query import QueryRequest
from app.lib.connection_manager import ConnectionManager


class SpeechServicesFunctions:
    """
    Main functions class for the Speech Services plugin
    """

    def __init__(self, function_handler):
        self.function_handler = function_handler
        self.config = function_handler.config
        self.secrets = function_handler.secrets
        self._logger = logging.getLogger(__name__)
        self.connection_manager = ConnectionManager()
        self.websocket_manager = self.connection_manager
        self.content_session_manager = function_handler.content_session_manager
        self.notification_manager = function_handler.notification_manager
        self.redis_ops = self.content_session_manager.redis_ops
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    async def handle_speech_start(
        self,
        user_query: QueryRequest,
        user_id: str,
        content_session_id: str,
        client_id: str,
    ):
        """Handle start of speech session"""
        session_id = f"speech_{user_id}_{client_id}"
        websocket_client = await self.connection_manager.get_websocket_client()

        # Initialize OpenAI session configuration
        config_message = {
            "type": "session.update",
            "session": {
                "voice": user_query.plugin_data.get("voice", "alloy"),
                "turn_detection": {"mode": "server"},
            },
        }

        # Store session info
        self.active_sessions[session_id] = {
            "user_id": user_id,
            "client_id": client_id,
            "content_session_id": content_session_id,
            "config": user_query.plugin_data,
        }

        await websocket_client.send_message(
            user_id,
            {
                "type": "speech_session_started",
                "session_id": session_id,
                "config": config_message,
            },
        )

        # Create notification for session start
        notification_data = {
            "toast_message": "Speech session started",
            "toast_type": "text",
            "persistent": False,
        }
        await self.notification_manager.create_notification(
            user_id, content_session_id, notification_data
        )

    async def handle_text_input(
        self,
        user_query: QueryRequest,
        user_id: str,
    ):
        """Handle text input for TTS"""
        websocket_client = await self.connection_manager.get_websocket_client()

        message = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_query.messages[-1].content}
                ],
            },
        }

        await websocket_client.send_message(user_id, message)
        await websocket_client.send_message(
            user_id,
            {"type": "response.create", "response": {"modalities": ["text", "audio"]}},
        )

    async def handle_audio_input(
        self,
        user_query: QueryRequest,
        user_id: str,
    ):
        """Handle audio input for STT"""
        websocket_client = await self.connection_manager.get_websocket_client()

        # Extract audio data from plugin_data
        audio_chunk = user_query.plugin_data.get("audio_chunk")
        if not audio_chunk:
            return

        message = {
            "type": "input_audio_buffer.append",
            "input_audio": {
                "format": "wav",
                "chunk": audio_chunk,
            },
        }

        await websocket_client.send_message(user_id, message)

    async def handle_speech_end(
        self,
        user_id: str,
        content_session_id: str,
        client_id: str,
    ):
        """Handle end of speech session"""
        session_id = f"speech_{user_id}_{client_id}"

        if session_id in self.active_sessions:
            websocket_client = await self.connection_manager.get_websocket_client()

            # Cleanup session
            self.active_sessions.pop(session_id)

            # Notify client
            await websocket_client.send_message(
                user_id, {"type": "speech_session_ended", "session_id": session_id}
            )

            # Create notification for session end
            notification_data = {
                "toast_message": "Speech session ended",
                "toast_type": "text",
                "persistent": False,
            }
            await self.notification_manager.create_notification(
                user_id, content_session_id, notification_data
            )
