# app/lib/user_manager.py

from datetime import datetime, timezone
import logging
import traceback
import json
from uuid import uuid4
from fastapi import HTTPException
from tenacity import retry, wait_fixed, stop_after_attempt, RetryError
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis

from app.lib.content_session_manager import ContentSessionManager
from app.lib.permissions_token_manager import PermissionsTokenManager
from app.lib.mongo_operations import MongoOperations
from app.schemas.mongo_schema import generate_user_data


class UserManager:
    def __init__(
        self,
        content_session_manager: ContentSessionManager,
        permissions_token_manager: PermissionsTokenManager,
        mongo_client: AsyncIOMotorClient,
        redis_client: redis.Redis,
        config: dict,
        secrets: dict,
    ):
        self.content_session_manager = content_session_manager
        self.permissions_token_manager = permissions_token_manager
        self.mongo_ops = MongoOperations(mongo_client)
        self.redis_client = redis_client
        self.config = config
        self.secrets = secrets
        self.logger = logging.getLogger(__name__)
        self.logger.debug("UserManager initialized")

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def create_user(self, user_id: str, access_token: str) -> str:
        """
        Create a new user and store user, access token, and permissions token data in MongoDB.

        Args:
            user_id (str): The user ID.
            access_token (str): The access token.

        Returns:
            str: The user ID if creation is successful.

        Raises:
            HTTPException: If an error occurs during user creation.
        """
        try:
            permissions_token = (
                await self.permissions_token_manager.generate_permissions_token(user_id)
            )

            permissions_token_id = permissions_token["_id"]

            created_at = datetime.now(timezone.utc).isoformat()

            # Generate user data, access token data, and permissions token data
            user_data = await generate_user_data(
                user_id, access_token, permissions_token_id, created_at
            )

            # Save data to MongoDB
            await self.mongo_ops.create_user_in_mongo(user_data)

            return user_id
        except RetryError as re:
            self.logger.error(
                f"Retry failed during user creation: {re}\n{traceback.format_exc()}"
            )
            raise HTTPException(
                status_code=500, detail="Internal Server Error after retries"
            )
        except Exception as e:
            self.logger.error(f"Error creating user: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def create_user_with_auth_provider(
        self, auth_provider: str, auth_user_id: str, access_token: str
    ) -> str:
        access_token, auth_provider, auth_user_id
        """
        Create a new user with an auth provider and store the user, access token, and auth provider data in MongoDB.

        Args:
            auth_provider (str): The authentication provider (e.g., "creative_passport").
            auth_user_id (str): The ID provided by the authentication provider.
            access_token (str): The access token to associate with the new user.

        Returns:
            str: The user ID if creation is successful.

        Raises:
            HTTPException: If an error occurs during user creation.
        """
        try:
            # Generate a new user ID
            user_id = str(uuid4())

            # Generate the permissions token
            permissions_token = (
                await self.permissions_token_manager.generate_permissions_token(user_id)
            )
            permissions_token_id = permissions_token["_id"]

            # Capture the current timestamp
            created_at = datetime.now(timezone.utc).isoformat()

            # Generate user data, access token data, and permissions token data
            user_data = await generate_user_data(
                user_id,
                access_token,
                permissions_token_id,
                created_at,
                auth_provider,
                auth_user_id,
            )

            # Save the user data in MongoDB
            await self.mongo_ops.create_user_in_mongo(user_data)

            return user_id
        except RetryError as re:
            self.logger.error(
                f"Retry failed during user creation: {re}\n{traceback.format_exc()}"
            )
            raise HTTPException(
                status_code=500, detail="Internal Server Error after retries"
            )
        except Exception as e:
            self.logger.error(
                f"Error creating user with auth provider: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def get_user_data_by_auth_provider(
        self, auth_provider: str, auth_user_id: str
    ) -> dict:
        """
        Retrieve user data based on auth provider and auth ID.

        Args:
            auth_provider (str): The authentication provider.
            auth_user_id (str): The User ID provided by the authentication provider.

        Returns:
            dict: The user data if found, otherwise None.

        Raises:
            HTTPException: If an error occurs during user retrieval.
        """
        try:
            user_data = await self.mongo_ops.get_user_by_auth_provider(
                auth_provider, auth_user_id
            )

            return user_data if user_data else None
        except RetryError as re:
            self.logger.error(
                f"Retry failed during user retrieval: {re}\n{traceback.format_exc()}"
            )
            raise HTTPException(
                status_code=500, detail="Internal Server Error after retries"
            )
        except Exception as e:
            self.logger.error(
                f"Error retrieving user by auth provider: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def get_user_data(self, user_id: str) -> dict:
        """
        Retrieve user data for a given user ID.

        Args:
            user_id (str): The user ID.

        Returns:
            dict: The user data, or None if not found.

        Raises:
            HTTPException: If an error occurs during data retrieval.
        """
        try:
            # Attempt to retrieve user from MongoDB
            user_data = await self.mongo_ops.get_user_from_mongo(user_id)
            return user_data if user_data else None
        except RetryError as re:
            self.logger.error(
                f"Retry failed during data retrieval: {re}\n{traceback.format_exc()}"
            )
            raise HTTPException(
                status_code=500, detail="Internal Server Error after retries"
            )
        except Exception as e:
            self.logger.error(
                f"Error retrieving user data: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def update_user(self, user_id: str, update_fields: dict):
        """
        Update user data for a given user ID.

        Args:
            user_id (str): The user ID.
            update_fields (dict): The fields to update in the user data.

        Raises:
            HTTPException: If an error occurs during data update.
        """
        try:
            # Update user data in MongoDB
            await self.mongo_ops.update_user_in_mongo(user_id, update_fields)
        except RetryError as re:
            self.logger.error(
                f"Retry failed during data update: {re}\n{traceback.format_exc()}"
            )
            raise HTTPException(
                status_code=500, detail="Internal Server Error after retries"
            )
        except Exception as e:
            self.logger.error(
                f"Error updating user data in MongoDB: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def delete_user(self, user_id: str):
        """
        Delete user data and associated sessions for a given user ID.

        Args:
            user_id (str): The user ID.

        Raises:
            HTTPException: If an error occurs during user deletion.
        """
        try:
            # Delete user data from MongoDB
            await self.mongo_ops.delete_user_from_mongo(user_id)
            # Delete sessions associated with the user
            await self.content_session_manager.delete_sessions_by_user(user_id)
        except Exception as e:
            self.logger.error(
                f"Error deleting user {user_id}: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def create_user_creation_token(self, access_token: str) -> dict:
        """
        Creates a unique user ID and associates it with a newly generated access token.

        The method generates a unique user ID, creates an access token, and stores the
        user creation token data in Redis with an expiration time. The access token and
        user ID are used to form the user creation token data.

        Args:
            access_token (str): The access token to associate with the new user.

        Returns:
            dict: A dictionary containing the generated user creation token.

        Raises:
            HTTPException: If an error occurs during token creation.
        """
        try:
            user_id = str(uuid4())
            user_creation_token_data = {"userId": user_id}
            user_creation_token_key = f"userCreationToken:{access_token}"

            # Store the user creation token data in Redis and set an expiration time of 1 minute
            await self.redis_client.set(
                user_creation_token_key, json.dumps(user_creation_token_data)
            )
            await self.redis_client.expire(user_creation_token_key, 60)

            return {"userCreationToken": {"accessToken": access_token}}
        except Exception as e:
            self.logger.error(
                f"Error generating user creation token: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def validate_user_creation_token(self, access_token: str) -> dict:
        """
        Validates the user creation token and retrieves the user ID.

        Args:
            access_token (str): The access token to validate.

        Returns:
            str: The user ID if the token is valid.

        Raises:
            HTTPException: If the token is invalid or an error occurs during validation.
        """
        try:
            token_key = f"userCreationToken:{access_token}"
            user_creation_token = await self.redis_client.get(token_key)
            if user_creation_token:
                return json.loads(user_creation_token)
            else:
                raise HTTPException(
                    status_code=403, detail="Invalid user creation token"
                )
        except Exception as e:
            self.logger.error(
                f"Error validating user creation token: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def delete_user_creation_token(self, access_token: str):
        """
        Deletes a user creation token from Redis.

        Args:
            access_token (str): The access token to delete.

        Raises:
            HTTPException: If an error occurs during token deletion.
        """
        try:
            result = await self.redis_client.delete(f"userCreationToken:{access_token}")
            if result != 1:
                self.logger.warning(
                    f"User creation token {access_token} not found in Redis"
                )
        except Exception as e:
            self.logger.error(
                f"Unexpected error occurred while deleting user creation token {access_token}: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def validate_user_access_token(
        self, access_token_id: str, user_id: str
    ) -> bool:
        """
        Validates the user access token by checking its existence in MongoDB.

        Args:
            access_token_id (str): The access token ID to validate.
            user_id (str): The user ID associated with the access token.

        Returns:
            bool: True if the access token is valid.

        Raises:
            HTTPException: If the access token is invalid or an error occurs during validation.
        """
        # Attempt to retrieve the access token from MongoDB
        user_data = await self.mongo_ops.get_access_token_from_mongo(access_token_id)

        # Check if user data was retrieved and matches the expected user ID
        if user_data and user_data["_id"] == user_id:
            return True
        else:
            self.logger.info(f"Invalid access token ID: {access_token_id}")
            raise HTTPException(status_code=403, detail="Invalid access token")

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def regenerate_access_token(
        self, user_id: str = None, auth_provider: str = None, auth_user_id: str = None
    ) -> dict:
        """
        Regenerates an access token for a user either by user_id or by auth_provider and auth_user_id.

        Args:
            user_id (str, optional): The user ID for direct access token regeneration.
            auth_provider (str, optional): The authentication provider, used with auth_user_id.
            auth_user_id (str, optional): The user ID provided by the authentication provider.

        Returns:
            dict: Contains the new access token and user_id if regeneration is successful.

        Raises:
            HTTPException: If the user is not found or if an error occurs during regeneration.
        """
        try:
            # Authenticate user by user_id or auth_provider and auth_user_id
            if user_id:
                user_data = await self.get_user_data(user_id)
            elif auth_provider and auth_user_id:
                user_data = await self.get_user_data_by_auth_provider(
                    auth_provider, auth_user_id
                )
            else:
                raise HTTPException(
                    status_code=400, detail="User ID or auth provider details required"
                )

            if not user_data:
                raise HTTPException(status_code=404, detail="User not found")

            # Generate new access token
            new_access_token = str(uuid4())
            await self.update_user(user_data["_id"], {"accessToken": new_access_token})

            return {"userId": user_data["_id"], "accessToken": new_access_token}

        except RetryError as re:
            self.logger.error(
                f"Retry failed during access token regeneration: {re}\n{traceback.format_exc()}"
            )
            raise HTTPException(
                status_code=500, detail="Internal Server Error after retries"
            )
