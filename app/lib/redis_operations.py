# app/lib/redis_operations.py

import json
import logging
from fastapi import HTTPException
from typing import Any, Dict, Optional, List
import redis.asyncio as redis


class RedisOperations:
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)

    # Create functions

    async def create_content_session_in_redis(
        self, content_session_data: Dict[str, Any], ttl: int = 3600
    ) -> None:
        try:
            content_session_id = content_session_data["_id"]
            await self.redis_client.set(
                content_session_id,
                json.dumps(content_session_data, default=str),
                ex=ttl,
            )
            self.logger.debug(
                f"Stored content session in Redis with ID: {content_session_id}"
            )
        except Exception as e:
            self.logger.error(f"Error storing content session in Redis: {e}")
            raise

    async def create_notification_in_redis(
        self, notification: Dict[str, Any], ttl: int = 3600
    ) -> None:
        try:
            user_id = notification["userId"]
            content_session_id = notification["contentSessionId"]
            notification_id = str(notification["_id"])
            key = f"notification:{user_id}:{content_session_id}:{notification_id}"

            # Ensure _id is a string for consistency with MongoDB
            notification["_id"] = str(notification["_id"])

            await self.redis_client.set(
                key, json.dumps(notification, default=str), ex=ttl
            )
            self.logger.debug(f"Stored notification in Redis with key: {key}")
        except Exception as e:
            self.logger.error(f"Error caching notification in Redis: {e}")
            raise

    async def create_notifications_in_redis(
        self, notifications: List[Dict[str, Any]], ttl: int = 3600
    ) -> None:
        try:
            pipeline = self.redis_client.pipeline()
            for notification in notifications:
                user_id = notification["userId"]
                content_session_id = notification["contentSessionId"]
                notification_id = str(notification["_id"])
                key = f"notification:{user_id}:{content_session_id}:{notification_id}"

                # Ensure _id is a string for consistency with MongoDB
                notification["_id"] = str(notification["_id"])

                pipeline.set(key, json.dumps(notification, default=str), ex=ttl)

            await pipeline.execute()
            self.logger.debug(f"Stored {len(notifications)} notifications in Redis")
        except Exception as e:
            self.logger.error(f"Error caching multiple notifications in Redis: {e}")
            raise

    # Get functions

    async def get_content_session_from_redis(
        self, user_id: str, content_session_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            content_session = await self.redis_client.get(content_session_id)
            if content_session:
                self.logger.debug(
                    f"Retrieved content session from Redis with ID: {content_session_id}"
                )
                session_data = json.loads(content_session)
                if session_data.get("userId") != user_id:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "status": "error",
                            "data": "user_id_mismatch",
                            "message": f"User ID {user_id} does not match the content session user ID {session_data.get('userId')}",
                        },
                    )
                return session_data
            return None
        except HTTPException as e:
            self.logger.error(e)
            raise
        except Exception as e:
            self.logger.error(f"Error retrieving content session from Redis: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "data": "internal_server_error",
                    "message": "Error retrieving content session from Redis",
                },
            )

    async def get_unseen_notifications_from_redis(
        self, user_id: str, content_session_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        try:
            pattern = f"notification:{user_id}:{content_session_id}:*"
            keys = await self.redis_client.keys(pattern)

            if not keys:
                return None

            notifications = await self.redis_client.mget(keys)
            parsed_notifications = [
                json.loads(notif) for notif in notifications if notif
            ]

            return parsed_notifications if parsed_notifications else None
        except Exception as e:
            self.logger.error(f"Error retrieving unseen notifications from Redis: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    # Delete functions

    async def delete_seen_notification_from_redis(
        self, user_id: str, content_session_id: str, notification_id: str
    ) -> None:
        try:
            key = f"notification:{user_id}:{content_session_id}:{notification_id}"
            await self.redis_client.delete(key)
            self.logger.debug(f"Deleted seen notification from Redis with key: {key}")
        except Exception as e:
            self.logger.error(f"Error removing seen notification from Redis: {e}")
            raise
