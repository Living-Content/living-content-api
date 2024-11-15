# app/lib/notification_manager.py

import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from app.lib.mongo_operations import MongoOperations
from app.lib.redis_operations import RedisOperations
from app.schemas.mongo_schema import generate_notification_data


class NotificationManager:
    def __init__(self, mongo_client, redis_client, websocket_client):
        self.mongo_client = mongo_client
        self.redis_client = redis_client
        self.websocket_client = websocket_client
        self.mongo_ops = MongoOperations(mongo_client)
        self.redis_ops = RedisOperations(redis_client)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("NotificationManager initialized")

    @classmethod
    async def create(cls, connection_manager):
        """Factory method to create a NotificationManager instance with required clients"""
        mongo_client = await connection_manager.get_mongo_client()
        redis_client = await connection_manager.get_redis_client()
        websocket_client = await connection_manager.get_websocket_client()
        return cls(mongo_client, redis_client, websocket_client)

    async def get_unseen_notifications(
        self, user_id: str, content_session_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        self.logger.debug(f"Fetching unseen notifications for user {user_id}")
        try:
            notifications = await self.redis_ops.get_unseen_notifications_from_redis(
                user_id, content_session_id
            )
            if notifications is None:
                notifications = (
                    await self.mongo_ops.get_unseen_notifications_from_mongo(
                        user_id, content_session_id
                    )
                )
                if notifications:
                    await self.redis_ops.create_notifications_in_redis(notifications)
            return notifications
        except Exception as e:
            self.logger.error(f"Error fetching unseen notifications: {e}")
            raise e

    async def update_notification_as_seen(
        self, user_id: str, content_session_id: str, notification_id: str
    ):
        self.logger.debug(
            f"Marking notification {notification_id} as seen for user {user_id}"
        )
        try:
            seen_at = datetime.now(timezone.utc)
            updated_notification = (
                await self.mongo_ops.update_notification_as_seen_in_mongo(
                    user_id, notification_id, seen_at
                )
            )
            self.logger.debug(
                f"[User {user_id}] Successfully marked notification {notification_id} as seen"
            )

            # Delete the seen notification from Redis
            await self.redis_ops.delete_seen_notification_from_redis(
                user_id, content_session_id, notification_id
            )

            # Send WebSocket message back to user
            await self.websocket_client.send_message(
                user_id,
                {
                    "type": "update_notification_as_seen",
                    "status": "success",
                    "message": "Notifications updated",
                    "notification_id": notification_id,
                },
            )

            self.logger.debug(
                f"[User {user_id}] Sending WebSocket confirmation for notification {notification_id}"
            )

            return updated_notification
        except Exception as e:
            self.logger.error(f"Error marking notification as seen: {e}")
            await self.websocket_client.send_message(
                user_id,
                {
                    "type": "update_notification_as_seen",
                    "status": "error",
                    "message": "Failed to update notification",
                },
            )
            raise e

    async def update_unread_messages(
        self, user_id: str, content_session_id: str, unread_messages: bool
    ):
        self.logger.debug(f"Marking messages as read for user {user_id}")
        try:
            updated_content_session = (
                await self.mongo_ops.update_content_session_in_mongo(
                    user_id, content_session_id, {"unreadMessages": unread_messages}
                )
            )

            await self.redis_ops.create_content_session_in_redis(
                updated_content_session
            )

            # Send WebSocket message back to user
            await self.websocket_client.send_message(
                user_id,
                {
                    "type": "updated_unread_messages",
                    "status": "success",
                    "message": "Unread messages updated",
                    "data": {
                        "contentSessionId": content_session_id,
                        "unreadMessages": unread_messages,
                    },
                },
            )
        except Exception as e:
            self.logger.error(f"Error updating unread messages: {e}")
            await self.websocket_client.send_message(
                user_id,
                {
                    "type": "updated_unread_messages",
                    "status": "error",
                    "message": "Failed to update unread messages",
                },
            )
            raise e

    async def create_notification(
        self,
        user_id: str,
        content_session_id: str,
        notification: dict,
        notification_type="notification",
    ):
        try:
            notification_id = str(uuid.uuid4())
            created_at = datetime.now(timezone.utc).isoformat()

            self.logger.debug(
                f"Creating notification {notification_id} for user {user_id}"
            )

            self.logger.debug(f"Notification data: {notification}")
            notification_data = await generate_notification_data(
                notification_id,
                user_id,
                content_session_id,
                created_at,
                associated_message_id=notification.get("associated_message_id", None),
                associated_image=notification.get("associated_image", None),
                associated_task_id=notification.get("associated_task_id", None),
                toast_message=notification.get("toast_message", None),
                toast_type=notification.get("toast_type", "text"),
                associated_message=notification.get("associated_message", None),
                response_data=notification.get("response_data", None),
                persistent=notification.get("persistent", False),
            )

            # Prepare the message for WebSocketHandler
            websocket_message = {"type": notification_type, "data": notification_data}

            # Send the WebSocket message directly here
            await self.websocket_client.send_message(user_id, websocket_message)

            # Create notification in MongoDB using the original dict (with datetime objects)
            await self.mongo_ops.create_notification_in_mongo(notification_data)

            # Create notification in Redis using the serialized dict
            await self.redis_ops.create_notification_in_redis(notification_data)

        except Exception as e:
            self.logger.error(f"Error creating notification: {e}")
            raise e
