# app/lib/content_session_manager.py

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import HTTPException
from tenacity import RetryError, retry, stop_after_attempt, wait_fixed

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
        self._locks = {}  # Dictionary to store locks per session
        self.logger.info("ContentSessionManager initialized successfully")

    @asynccontextmanager
    async def _get_session_lock(self, session_id: str):
        """Get a lock for a specific session ID"""
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        try:
            await self._locks[session_id].acquire()
            yield
        finally:
            self._locks[session_id].release()
            # Clean up the lock if no one is waiting for it
            if not self._locks[session_id].locked():
                self._locks.pop(session_id, None)

    async def _safely_update_redis(self, content_session: dict):
        """Safely update Redis with a new version of content session"""
        try:
            # Get current version from Redis first
            current = await self.redis_ops.get_content_session_from_redis(
                content_session["userId"], content_session["_id"]
            )

            # Only update if new version is higher or there's no current version
            if not current or current.get("version", 0) < content_session.get(
                "version", 0
            ):
                await self.redis_ops.create_content_session_in_redis(content_session)
        except Exception as e:
            self.logger.error(f"Failed to update Redis: {e}")
            # Don't raise the exception - Redis is just a cache

    async def get_content_session_helper(
        self, content_session_id: str, user_id: str
    ) -> dict | None:
        """Helper function to get content session with proper versioning"""
        try:
            # Try Redis first
            content_session = await self.redis_ops.get_content_session_from_redis(
                user_id, content_session_id
            )

            # If found in Redis, verify it's not stale by checking MongoDB
            if content_session:
                mongo_session = await self.mongo_ops.get_content_session_from_mongo(
                    user_id, content_session_id
                )
                if mongo_session and mongo_session.get(
                    "version", 0
                ) > content_session.get("version", 0):
                    content_session = mongo_session
                    await self._safely_update_redis(content_session)
                return content_session

            # If not in Redis, get from MongoDB and cache it
            content_session = await self.mongo_ops.get_content_session_from_mongo(
                user_id, content_session_id
            )
            if content_session:
                await self._safely_update_redis(content_session)
            return content_session

        except ValueError as e:
            self.logger.error(f"Redis value error: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Internal server error",
                    "data": "internal_server_error",
                    "details": str(e),
                },
            )

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def create_content_session(self, user_id: str) -> dict:
        """Create a new content session with proper locking and versioning"""
        try:
            content_session_id = str(uuid.uuid4())
            current_time = datetime.now(UTC).isoformat()

            async with self._get_session_lock(content_session_id):
                # Start MongoDB transaction
                async with await self.mongo_client.start_session() as session:
                    async with session.start_transaction():
                        # Generate session data with initial version
                        content_session_data = await generate_content_session_data(
                            user_id, content_session_id, current_time
                        )
                        content_session_data["version"] = 1

                        # Create session in MongoDB
                        try:
                            await self.mongo_ops.create_content_session_in_mongo(
                                content_session_data
                            )
                        except Exception as e:
                            raise Exception(
                                f"Failed to create content session in MongoDB: {e}"
                            )

                        # Update user's active session
                        try:
                            update_fields = {
                                "activeContentSessionId": content_session_id,
                                "lastUpdated": current_time,
                            }
                            await self.mongo_ops.update_user_in_mongo(
                                user_id, update_fields
                            )
                        except Exception as e:
                            raise Exception(f"Failed to update user: {e}")

                # After successful transaction, update Redis
                try:
                    await self.redis_ops.create_content_session_in_redis(
                        content_session_data
                    )
                except Exception as e:
                    self.logger.error(f"Failed to create content session in Redis: {e}")
                    # Don't raise exception for Redis failures

                return content_session_data

        except RetryError as re:
            self.logger.error(f"Retry failed during content session creation: {re}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Failed to create content session after retries",
                    "data": "internal_server_error_with_retries",
                    "details": str(re),
                },
            )
        except Exception as e:
            self.logger.error(f"Failed to create content session: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Failed to create content session",
                    "data": "internal_server_error",
                    "details": str(e),
                },
            )

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def get_content_session(self, user_id: str, content_session_id: str) -> dict:
        """Get content session with versioning support"""
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
                    "version": content_session.get("version", 0),
                }

            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Content Session not found",
                    "data": "no_content_session",
                },
            )
        except RetryError as re:
            self._handle_retry_error(re)

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3), reraise=True)
    async def get_content_session_data(
        self, user_id: str, content_session_id: str
    ) -> dict:
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
    ) -> dict:
        """Update content session with optimistic locking"""
        async with self._get_session_lock(content_session_id):
            try:
                # Get current version
                current_session = await self.mongo_ops.get_content_session_from_mongo(
                    user_id, content_session_id
                )
                if not current_session:
                    raise HTTPException(
                        status_code=404,
                        detail={
                            "message": "Content Session not found",
                            "data": "no_content_session",
                        },
                    )

                # Increment version and update timestamp
                current_version = current_session.get("version", 0)
                new_data["version"] = current_version + 1
                new_data["lastUpdated"] = datetime.now(UTC).isoformat()

                # Update with optimistic locking
                updated_session = await self.mongo_ops.update_content_session_in_mongo(
                    user_id,
                    content_session_id,
                    new_data,
                )

                if not updated_session:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "message": "Content session was modified by another process",
                            "data": "version_conflict",
                        },
                    )

                # Update Redis after successful MongoDB update
                await self._safely_update_redis(updated_session)
                return updated_session

            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error updating content session: {e}")
                raise HTTPException(
                    status_code=500,
                    detail={
                        "message": "Failed to update content session",
                        "data": "internal_server_error",
                        "details": str(e),
                    },
                )

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def delete_content_session(self, user_id: str, content_session_id: str):
        """Delete content session with proper locking"""
        async with self._get_session_lock(content_session_id):
            try:
                # Use transaction to ensure atomicity
                async with await self.mongo_client.start_session() as session:
                    async with session.start_transaction():
                        await self.mongo_ops.delete_content_session_in_mongo(
                            user_id, content_session_id, session=session
                        )
                        # Update user's active session if necessary
                        user = await self.mongo_ops.get_user_from_mongo(user_id)
                        if (
                            user
                            and user.get("activeContentSessionId") == content_session_id
                        ):
                            await self.mongo_ops.update_user_in_mongo(
                                user_id, {"activeContentSessionId": None}
                            )

                # After successful MongoDB deletion, remove from Redis
                await self.redis_ops.delete_content_session_in_redis(content_session_id)

            except Exception as e:
                self.logger.error(f"Error deleting content session: {e}")
                raise HTTPException(
                    status_code=500,
                    detail={
                        "message": "Failed to delete content session",
                        "data": "internal_server_error",
                        "details": str(e),
                    },
                )

    async def delete_sessions_by_user(self, user_id: str):
        """Delete all sessions for a user with proper locking"""
        try:
            sessions = await self.mongo_ops.get_all_content_sessions(user_id)
            for session in sessions:
                await self.delete_content_session(user_id, session["_id"])

            # Update user's active session to None
            await self.mongo_ops.update_user_in_mongo(
                user_id, {"activeContentSessionId": None}
            )

        except Exception as e:
            self.logger.error(f"Error deleting content sessions: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Failed to delete content sessions",
                    "data": "internal_server_error",
                    "details": str(e),
                },
            )

    def _handle_retry_error(self, re: RetryError):
        """Helper method to handle retry errors consistently"""
        last_attempt = re.last_attempt
        if last_attempt and last_attempt.exception():
            exception = last_attempt.exception()
            self.logger.error(
                f"Retry failed: {re} with exception: {exception}", exc_info=True
            )
            if isinstance(exception, HTTPException):
                raise exception

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Operation failed after retries",
                "data": "internal_server_error_with_retries",
                "details": str(re),
            },
        )
