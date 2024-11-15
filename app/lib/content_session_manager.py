# app/lib/content_session_manager.py

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict
from tenacity import retry, wait_fixed, stop_after_attempt, RetryError
from fastapi import HTTPException

from app.lib.mongo_operations import MongoOperations
from app.lib.redis_operations import RedisOperations
from app.schemas.mongo_schema import generate_content_session_data


class ContentSessionManager:
    def __init__(self, mongo_client, redis_client):
        """Initialize the ContentSessionManager with required clients.

        Args:
            mongo_client: AsyncIOMotorClient instance
            redis_client: Redis client instance
        """
        if not mongo_client or not redis_client:
            raise ValueError("Both mongo_client and redis_client must be provided")

        self.mongo_client = mongo_client
        self.redis_client = redis_client
        self.mongo_ops = MongoOperations(mongo_client)
        self.redis_ops = RedisOperations(redis_client)
        self.logger = logging.getLogger(__name__)
        self.logger.info("ContentSessionManager initialized successfully")

    # Helper function

    async def get_content_session_helper(self, content_session_id: str, user_id: str):
        try:
            content_session = await self.redis_ops.get_content_session_from_redis(
                user_id, content_session_id
            )
        except ValueError as e:
            self.logger.error(f"Redis value error: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Internal server error (this is bad)",
                    "data": "internal_server_error",
                    "details": str(e),
                },
            )

        if content_session:
            return content_session

        content_session = await self.mongo_ops.get_content_session_from_mongo(
            user_id, content_session_id
        )
        if content_session:
            await self.redis_ops.create_content_session_in_redis(content_session)
        return content_session

    # Main functions

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def create_content_session(self, user_id: str):
        try:
            content_session_id = str(uuid.uuid4())
            current_time = datetime.now(timezone.utc).isoformat()

            content_session_data = await generate_content_session_data(
                user_id, content_session_id, current_time
            )

            try:
                await self.mongo_ops.create_content_session_in_mongo(
                    content_session_data
                )
            except Exception as e:
                raise Exception(f"Failed to create content session in MongoDB")

            try:
                await self.redis_ops.create_content_session_in_redis(
                    content_session_data
                )
            except Exception as e:
                raise Exception(f"Failed to create content session in Redis")

            try:
                update_fields = {
                    "activeContentSessionId": content_session_id,
                }
                updated_user_id = await self.mongo_ops.update_user_in_mongo(
                    user_id, update_fields
                )
                self.logger.info(f"User {updated_user_id} updated successfully.")
            except Exception as e:
                self.logger.error(f"Error updating user: {e}")
                raise HTTPException(
                    status_code=500,
                    detail={
                        "message": "Internal server error (this is bad)",
                        "data": "internal_server_error",
                        "details": str(e),
                    },
                )

            return content_session_data
        except RetryError as re:
            self.logger.error(f"Retry failed during content session creation: {re}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Internal server error (this is extra bad)",
                    "data": "internal_server_error_with_retries",
                    "details": str(re),
                },
            )
        except Exception as e:
            self.logger.error(f"Failed to create content session: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Internal server error (this is bad)",
                    "data": "internal_server_error",
                    "details": str(e),
                },
            )

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def get_content_session(self, user_id: str, content_session_id: str) -> Dict:
        try:
            content_session = await self.get_content_session_helper(
                content_session_id, user_id
            )
            if content_session:
                self.logger.debug(f"Content session retrieved: {content_session_id}")
                return {
                    "_id": content_session["_id"],
                    "userId": content_session["userId"],
                    "createdAt": content_session["createdAt"],
                    "lastUpdated": content_session["lastUpdated"],
                    "name": content_session["name"],
                }

            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Content Session not found",
                    "data": "no_content_session",
                },
            )
        except RetryError as re:
            last_attempt = re.last_attempt
            if last_attempt:
                exception = last_attempt.exception()
                self.logger.error(
                    f"Retry failed during content session retrieval: {re} with exception: {exception}",
                    exc_info=True,
                )
                if isinstance(exception, HTTPException):
                    raise exception
                else:
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "message": "Internal server error (this is extra bad)",
                            "data": "internal_server_error_with_retries",
                            "details": str(exception),
                        },
                    )
            else:
                self.logger.error(
                    f"Retry failed during content session retrieval: {re}",
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=500,
                    detail={
                        "message": "Internal server error (this is extra bad)",
                        "data": "internal_server_error_with_retries",
                        "details": str(re),
                    },
                )
        except Exception as e:
            self.logger.error(f"Error retrieving content session: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Internal server error (this is bad)",
                    "data": "internal_server_error",
                    "details": str(e),
                },
            )

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3), reraise=True)
    async def get_content_session_data(
        self, user_id: str, content_session_id: str
    ) -> Dict:
        content_session = await self.get_content_session_helper(
            content_session_id, user_id
        )
        if content_session:
            self.logger.debug(f"Content session retrieved: {content_session_id}")
            session_data = content_session.get("sessionData", {})
            return session_data
        else:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Content Session not found",
                    "data": "no_content_session",
                },
            )

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3), reraise=True)
    async def update_content_session(
        self,
        user_id: str,
        content_session_id: str,
        new_data: dict,
    ):
        try:
            updated_content_session = (
                await self.mongo_ops.update_content_session_in_mongo(
                    user_id, content_session_id, new_data
                )
            )
            await self.redis_ops.create_content_session_in_redis(
                updated_content_session
            )

            # Return a valid success response
            return {"message": "Content session updated successfully"}
        except Exception as e:
            self.logger.error(f"Error updating content session: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Internal server error (this is bad)",
                    "data": "internal_server_error",
                    "details": str(e),
                },
            )

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def delete_content_session(self, user_id: str, content_session_id: str):
        try:
            await self.mongo_ops.delete_content_session_in_mongo(
                user_id, content_session_id
            )
            await self.redis_ops.delete_content_session_in_redis(content_session_id)
        except RetryError as re:
            self.logger.error(f"Retry failed during content session deletion: {re}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Internal server error (this is extra bad)",
                    "data": "internal_server_error_with_retries",
                    "details": str(re),
                },
            )
        except Exception as e:
            self.logger.error(f"Error deleting content session: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Internal server error (this is bad)",
                    "data": "internal_server_error",
                    "details": str(e),
                },
            )

    async def delete_sessions_by_user(self, user_id: str):
        try:
            sessions = await self.mongo_ops.get_all_content_sessions(user_id)
            for session in sessions:
                await self.delete_content_session(user_id, session["_id"])
        except Exception as e:
            self.logger.error(f"Error deleting content sessions: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Internal server error (this is bad)",
                    "data": "internal_server_error",
                    "details": str(e),
                },
            )
