import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from tenacity import RetryError, retry, stop_after_attempt, wait_fixed

from app.lib.mongo_operations import MongoOperations
from app.schemas.mongo_schema import generate_permissions_token_data


class PermissionsTokenManager:
    def __init__(self, mongo_client):
        self.mongo_ops = MongoOperations(mongo_client)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("PermissionsTokenManager initialized")

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def generate_permissions_token(self, user_id: str):
        """
        Generates a new permission token for a user.

        Args:
            user_id (str): The ID of the user.

        Returns:
            str: The generated permission token.

        Raises:
            HTTPException: If an error occurs during token generation.
        """
        try:
            permissions_token_id = str(uuid.uuid4())
            created_at = datetime.now(UTC).isoformat()

            # Generate token data
            token_data = await generate_permissions_token_data(
                user_id, permissions_token_id, created_at
            )

            # Debug: Log the type and content of token_data
            self.logger.debug(f"Token data type: {type(token_data)}")
            self.logger.debug(f"Token data content: {token_data}")

            # Ensure token_data is a dictionary
            if not isinstance(token_data, dict):
                raise ValueError(
                    f"Expected dict for token_data, got {type(token_data)}"
                )

            # Store in MongoDB
            await self.mongo_ops.create_permissions_token_in_mongo(token_data)

            return token_data
        except ValueError as ve:
            self.logger.error(f"Invalid data type for permissions token: {ve}")
            raise HTTPException(
                status_code=500, detail=f"Internal Server Error: {ve!s}"
            )
        except RetryError as re:
            self.logger.error(f"Retry failed during permission token generation: {re}")
            raise HTTPException(
                status_code=500, detail="Internal Server Error after retries"
            )
        except Exception as e:
            self.logger.error(f"Error generating permission token: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def get_permission_token_data(self, user_id: str):
        """
        Retrieves the data associated with a permission token.

        Args:
            user_id (str): The user ID associated with the token.

        Returns:
            dict: The token data.

        Raises:
            HTTPException: If an error occurs during data retrieval.
        """
        try:
            token_data = await self.mongo_ops.get_permissions_token_from_mongo(user_id)
            return token_data
        except RetryError as re:
            self.logger.error(f"Retry failed during permission token retrieval: {re}")
            raise HTTPException(
                status_code=500, detail="Internal Server Error after retries"
            )
        except Exception as e:
            self.logger.error(f"Error retrieving permission token data: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def update_permission_token(self, user_id: str, update_fields: dict):
        """
        Updates the data associated with a permission token.

        Args:
            user_id (str): The user ID associated with the token.
            update_fields (dict): The fields to update in the token data.

        Raises:
            HTTPException: If an error occurs during data update.
        """
        try:
            # Update in MongoDB
            await self.mongo_ops.update_permissions_token_in_mongo(
                user_id, update_fields
            )
        except RetryError as re:
            self.logger.error(f"Retry failed during permission token update: {re}")
            raise HTTPException(
                status_code=500, detail="Internal Server Error after retries"
            )
        except Exception as e:
            self.logger.error(f"Error updating permission token: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def revoke_permission_token(self, user_id: str, admin_user_id: str):
        """
        Revokes a permission token.

        Args:
            user_id (str): The user ID associated with the permission token to revoke.
            admin_user_id (str): The ID of the admin user performing the revocation.

        Raises:
            HTTPException: If the admin user is not authorized to revoke tokens or if an error occurs during revocation.
        """
        try:
            # Verify admin privileges (this should be implemented according to your authentication system)
            if not await self.is_admin(admin_user_id):
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to revoke tokens.",
                )

            # Delete from MongoDB
            await self.mongo_ops.delete_permissions_token_from_mongo(user_id)
        except RetryError as re:
            self.logger.error(f"Retry failed during permission token revocation: {re}")
            raise HTTPException(
                status_code=500, detail="Internal Server Error after retries"
            )
        except HTTPException as he:
            raise he  # Re-raise HTTP exceptions
        except Exception as e:
            self.logger.error(f"Error revoking permission token: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def is_admin(self, user_id: str) -> bool:
        """
        Checks if a user has admin privileges.

        Args:
            user_id (str): The ID of the user to check.

        Returns:
            bool: True if the user is an admin, False otherwise.

        Note: This is a placeholder method. Implement according to your authentication system.
        """
        # TODO: Implement admin check logic
        self.logger.warning("Admin check not implemented. Returning False by default.")
        return False

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    async def verify_permission_token(self, user_id: str, token: str) -> bool:
        """
        Verifies if a given permission token is valid for a user.

        Args:
            user_id (str): The ID of the user.
            token (str): The permission token to verify.

        Returns:
            bool: True if the token is valid, False otherwise.

        Raises:
            HTTPException: If an error occurs during token verification.
        """
        try:
            token_data = await self.get_permission_token_data(user_id)
            if token_data and token_data.get("token") == token:
                return True
            return False
        except RetryError as re:
            self.logger.error(
                f"Retry failed during permission token verification: {re}"
            )
            raise HTTPException(
                status_code=500, detail="Internal Server Error after retries"
            )
        except Exception as e:
            self.logger.error(f"Error verifying permission token: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")
