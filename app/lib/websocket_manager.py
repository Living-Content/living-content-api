# app/lib/websocket_manager.py

import logging
import json
import uuid
from typing import Tuple, Dict, Any
from fastapi import WebSocket
from motor.motor_asyncio import AsyncIOMotorClient
from app.lib.mongo_operations import MongoOperations
from app.lib.connection_manager import ConnectionManager
from app.lib.notification_manager import NotificationManager
import asyncio
import os


class WebSocketManager:
    def __init__(
        self,
        connection_manager: ConnectionManager,
        notification_manager: NotificationManager,
    ):
        self.logger = logging.getLogger(__name__)
        self.connection_manager = connection_manager
        self.notification_manager = (
            notification_manager  # Now stores the instance directly
        )
        self.worker_id = os.getpid()
        self.logger.debug(f"WebSocketManager initialized for worker {self.worker_id}")

    async def verify_user_exists(
        self, user_id: str, access_token: str, mongo_client: AsyncIOMotorClient
    ) -> bool:
        try:
            mongo_ops = MongoOperations(mongo_client)
            user_data = await mongo_ops.get_user_from_mongo(user_id)
            return (
                user_data is not None and user_data.get("accessToken") == access_token
            )
        except Exception as e:
            self.logger.error(f"Error validating user {user_id}: {e}")
            return False

    async def authenticate_user(
        self, websocket: WebSocket, mongo_client: AsyncIOMotorClient
    ) -> Tuple[bool, str]:
        try:
            auth_data = await websocket.receive_text()
            self.logger.debug(
                f"Worker {self.worker_id} received auth data: {auth_data}"
            )
            auth_message = json.loads(auth_data)

            if auth_message.get("type") != "auth" or not auth_message.get(
                "accessToken"
            ):
                return False, ""

            user_id = auth_message.get("userId")
            access_token = auth_message.get("accessToken")

            if not user_id:
                return False, ""

            # Verify user exists and tokens match
            is_valid = await self.verify_user_exists(
                user_id, access_token, mongo_client
            )

            if not is_valid:
                return False, ""

            return True, user_id

        except Exception as e:
            self.logger.error(f"Authentication error in worker {self.worker_id}: {e}")
            return False, ""

    async def register_connection(self, user_id: str) -> str:
        """Register a new connection for a user"""
        redis_client = await self.connection_manager.get_redis_client()
        try:
            # Get existing connections
            existing_connections = await redis_client.hget(
                "websocket_connections", user_id
            )
            connection_time = asyncio.get_event_loop().time()

            new_connection = {
                "worker_id": self.worker_id,
                "connected_at": connection_time,
                "client_id": str(uuid.uuid4()),
            }

            if existing_connections:
                try:
                    connections_data = json.loads(existing_connections)
                    if isinstance(connections_data, dict):
                        # Convert legacy format to list
                        connections_data = [connections_data]
                    connections_data.append(new_connection)
                except (json.JSONDecodeError, TypeError):
                    connections_data = [new_connection]
            else:
                connections_data = [new_connection]

            # Store in Redis
            await redis_client.hset(
                "websocket_connections", user_id, json.dumps(connections_data)
            )

            return new_connection["client_id"]

        except Exception as e:
            self.logger.error(f"Error registering connection for user {user_id}: {e}")
            raise

    async def handle_incoming_websocket_message(
        self, user_id: str, message_type: str, data: Dict[str, Any], client_id: str
    ):
        self.logger.debug(
            f"Worker {self.worker_id} handling message type: {message_type} for user: {user_id} client: {client_id}"
        )

        try:
            handler = getattr(
                self,
                f"handle_{message_type}",
                self.no_incoming_websocket_message_handler_found,
            )
            await handler(user_id, data, client_id)
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            return

    async def handle_update_notification_as_seen(
        self, user_id: str, data: Dict[str, Any], client_id: str
    ):
        notification_id = data.get("notificationId")
        content_session_id = data.get("contentSessionId")

        # Use the notification_manager instance directly
        await self.notification_manager.update_notification_as_seen(
            user_id, content_session_id, notification_id
        )

    async def handle_update_unread_messages(
        self, user_id: str, data: Dict[str, Any], client_id: str
    ):
        unread_messages = data.get("unreadMessageStatus")
        content_session_id = data.get("contentSessionId")

        # Use the notification_manager instance directly
        await self.notification_manager.update_unread_messages(
            user_id, content_session_id, unread_messages
        )

    async def handle_acknowledgement(
        self, user_id: str, data: Dict[str, Any], client_id: str
    ):
        """Handle acknowledgment messages from the WebSocket."""
        ack_sequence = data.get("sequence")
        if ack_sequence:
            websocket_client = await self.connection_manager.get_websocket_client()
            await websocket_client.handle_message_acknowledgement(
                user_id, ack_sequence, client_id
            )
        else:
            self.logger.warning(
                f"Invalid acknowledgment data from user {user_id} client {client_id}: {data}"
            )

    async def no_incoming_websocket_message_handler_found(
        self, user_id: str, data: Dict[str, Any], client_id: str
    ):
        websocket_client = await self.connection_manager.get_websocket_client()
        self.logger.debug(
            f"No message handler found for message type: {data.get('type')}"
        )
        await websocket_client.send_message(
            user_id,
            {
                "type": "no_user_message_handler_found",
                "status": "error",
                "message": "We could not process your message",
            },
        )
        self.logger.debug(
            f"Unhandled message type for user {user_id} client {client_id}: {data.get('type')}"
        )

    async def cleanup_connection(self, user_id: str, client_id: str = None):
        """Clean up when a user disconnects"""
        try:
            redis_client = await self.connection_manager.get_redis_client()
            connections = await redis_client.hget("websocket_connections", user_id)

            if not connections:
                return

            connections_data = json.loads(connections)

            if isinstance(connections_data, list):
                # Remove specific client connection
                if client_id:
                    connections_data = [
                        conn
                        for conn in connections_data
                        if conn.get("client_id") != client_id
                    ]
                else:
                    # Remove all connections for this worker
                    connections_data = [
                        conn
                        for conn in connections_data
                        if conn["worker_id"] != self.worker_id
                    ]

                if connections_data:
                    # Update Redis with remaining connections
                    await redis_client.hset(
                        "websocket_connections", user_id, json.dumps(connections_data)
                    )
                else:
                    # No more connections, remove the user entry
                    await redis_client.hdel("websocket_connections", user_id)
            else:
                # Legacy single connection cleanup
                if connections_data["worker_id"] == self.worker_id:
                    await redis_client.hdel("websocket_connections", user_id)

            self.logger.info(
                f"Cleaned up connection for user {user_id} on worker {self.worker_id}"
            )
        except Exception as e:
            self.logger.error(f"Error cleaning up connection: {e}")

    async def start_cleanup_listener(self):
        """Listen for cleanup messages from other workers"""
        redis_client = await self.connection_manager.get_redis_client()
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("websocket_cleanup")

        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message and message["type"] == "message":
                    data = json.loads(message["data"])
                    if data["old_worker"] == self.worker_id:
                        # Clean up the old connection
                        websocket_client = (
                            await self.connection_manager.get_websocket_client()
                        )
                        await websocket_client.disconnect(data["user_id"])
        except Exception as e:
            self.logger.error(f"Error in cleanup listener: {e}")
