# app/lib/mongo_operations.py

import logging
import traceback
from datetime import UTC, datetime, timedelta
from typing import Any

import inflection
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from app.lib.secrets import get_secrets


class MongoOperations:
    def __init__(self, mongo_client: AsyncIOMotorClient):
        self.mongo_client = mongo_client
        self.logger = logging.getLogger(__name__)
        self.secrets = get_secrets()

    # Helper functions
    @staticmethod
    def deep_merge(d1, d2):
        stack = [(d1, d2)]
        while stack:
            current_d1, current_d2 = stack.pop()
            for key, value in current_d2.items():
                if key in current_d1:
                    if isinstance(current_d1[key], dict) and isinstance(value, dict):
                        stack.append((current_d1[key], value))
                    elif isinstance(current_d1[key], list) and isinstance(value, list):
                        current_d1[key].extend(value)
                    else:
                        current_d1[key] = value
                else:
                    current_d1[key] = value
        return d1

    # Create operations
    async def create_user_in_mongo(self, user_data: dict[str, Any]) -> None:
        try:
            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("users")
            await mongo_instance.insert_one(user_data)
        except Exception as e:
            self.logger.error(f"Error storing user data: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def create_permissions_token_in_mongo(
        self, permissions_token_data: dict
    ) -> None:
        try:
            # Debug: Log the type and content of permissions_token_data
            self.logger.debug(
                f"Permissions token data type: {type(permissions_token_data)}"
            )
            self.logger.debug(
                f"Permissions token data content: {permissions_token_data}"
            )

            # Ensure permissions_token_data is a dictionary
            if not isinstance(permissions_token_data, dict):
                raise TypeError(
                    f"Expected dict for permissions_token_data, got {type(permissions_token_data)}"
                )

            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("permissions_tokens")
            await mongo_instance.insert_one(permissions_token_data)
        except TypeError as te:
            self.logger.error(f"Invalid data type for permissions token: {te}")
            raise HTTPException(
                status_code=500, detail=f"Internal Server Error: {te!s}"
            )
        except Exception as e:
            self.logger.error(
                f"Error storing permissions token data: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def create_content_session_in_mongo(
        self, content_session_data: dict[str, Any]
    ) -> None:
        try:
            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("content_sessions")
            await mongo_instance.insert_one(content_session_data)
        except Exception as e:
            self.logger.error(
                f"Error storing content session data: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def create_notification_in_mongo(
        self, notification_data: dict[str, Any]
    ) -> None:
        try:
            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("notifications")
            await mongo_instance.insert_one(notification_data)
        except Exception as e:
            self.logger.error(
                f"Error storing notification data: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    # Read operations
    async def get_user_from_mongo(self, user_id: str) -> dict[str, Any] | None:
        try:
            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("users")
            user_data = await mongo_instance.find_one({"_id": user_id})
            if user_data:
                return user_data
            else:
                self.logger.info(f"No user data found for user ID: {user_id}")
                return None
        except Exception as e:
            self.logger.error(
                f"Error retrieving user data from MongoDB: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def get_user_by_auth_provider(
        self, auth_provider: str, auth_user_id: str
    ) -> dict:
        """
        Retrieve a user document by auth provider and auth ID.
        """
        try:
            # Convert auth_provider to camelCase before querying
            camel_case_provider = inflection.camelize(auth_provider, False)

            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("users")

            # Use dot notation to query the nested field in authProviders
            user_data = await mongo_instance.find_one(
                {f"authProviders.{camel_case_provider}": auth_user_id}
            )

            if user_data:
                return user_data
            else:
                self.logger.info(
                    f"No user found for auth_provider '{camel_case_provider}' with auth_user_id '{auth_user_id}'"
                )
                return None
        except Exception as e:
            self.logger.error(
                f"Error retrieving user by auth_user_id from MongoDB: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def get_access_token_from_mongo(
        self, access_token: str
    ) -> dict[str, Any] | None:
        """
        Retrieves user data from MongoDB using the access token.

        Args:
            access_token_id (str): The access token ID to retrieve.

        Returns:
            Optional[Dict[str, Any]]: The user data if found, otherwise None.

        Raises:
            HTTPException: If an error occurs during retrieval.
        """
        try:
            # Get the users collection
            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("users")

            # Attempt to find the user data based on the access token
            user_data = await mongo_instance.find_one({"accessToken": access_token})

            # Log if no user data is found with the provided access token
            if not user_data:
                self.logger.info(
                    f"No user data found for access token ID: {access_token}"
                )
            return user_data

        except Exception as e:
            # Log the error and raise an HTTPException for internal server errors
            self.logger.error(
                f"Error retrieving user data from MongoDB: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def get_permissions_token_from_mongo(
        self, permissions_token_id: str
    ) -> dict[str, Any] | None:
        try:
            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("permissions_tokens")
            permissions_token_data = await mongo_instance.find_one(
                {"_id": permissions_token_id}
            )
            if permissions_token_data:
                return permissions_token_data
            else:
                self.logger.info(
                    f"No permissions token data found for permissions token ID: {permissions_token_id}"
                )
                return None
        except Exception as e:
            self.logger.error(
                f"Error retrieving permissions token data from MongoDB: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def get_content_session_from_mongo(
        self, user_id: str, content_session_id: str
    ) -> dict[str, Any] | None:
        try:
            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("content_sessions")
            content_session_data = await mongo_instance.find_one(
                {"_id": content_session_id, "userId": user_id}
            )
            if content_session_data:
                return content_session_data
            else:
                self.logger.info(
                    f"No content session data found for user ID: {user_id} and content session ID: {content_session_id}"
                )
                return None
        except Exception as e:
            self.logger.error(
                f"Error retrieving content session data from MongoDB: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def get_notification_from_mongo(
        self, notification_id: str
    ) -> dict[str, Any] | None:
        try:
            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("notifications")
            notification_data = await mongo_instance.find_one({"_id": notification_id})
            if notification_data:
                return notification_data
            else:
                self.logger.info(
                    f"No notification data found for notification ID: {notification_id}"
                )
                return None
        except Exception as e:
            self.logger.error(
                f"Error retrieving notification data from MongoDB: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def get_unseen_notifications_from_mongo(
        self, user_id: str, content_session_id: str
    ) -> list[dict[str, Any]] | None:
        try:
            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("notifications")
            notifications = await mongo_instance.find(
                {
                    "userId": user_id,
                    "contentSessionId": content_session_id,
                    "seen": False,
                }
            ).to_list(length=None)

            if not notifications:
                return None

            # Convert ObjectId to string for consistency with Redis
            for notification in notifications:
                notification["_id"] = str(notification["_id"])

            return notifications
        except Exception as e:
            self.logger.error(
                f"Error retrieving unseen notifications from MongoDB: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    # Update operations

    async def update_content_session_in_mongo(
        self, user_id: str, content_session_id: str, new_data: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            current_time = datetime.now(UTC).isoformat()
            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("content_sessions")

            # Get and update atomically
            existing_doc = await mongo_instance.find_one_and_update(
                {"userId": user_id, "_id": content_session_id},
                {"$set": {"_updating": True}},
                return_document=True,
            )

            if not existing_doc:
                self.logger.info(
                    f"No content session found to update with ID {content_session_id} for user {user_id}"
                )
                raise HTTPException(status_code=404, detail="Content session not found")

            # Perform the same merge logic as before
            existing_session_data = existing_doc.get("sessionData", {})
            updated_session_data = self.deep_merge(existing_session_data, new_data)
            existing_doc["sessionData"] = updated_session_data
            existing_doc["lastUpdated"] = current_time
            existing_doc.pop("_updating", None)

            # Use replace_one to maintain exact same update behavior
            result = await mongo_instance.replace_one(
                {"userId": user_id, "_id": content_session_id, "_updating": True},
                existing_doc,
            )

            if result.modified_count:
                self.logger.info(
                    f"Updated content session with ID {content_session_id} for user {user_id}"
                )
                return existing_doc
            else:
                self.logger.error(
                    f"Failed to update content session with ID {content_session_id} for user {user_id}"
                )
                raise HTTPException(
                    status_code=500, detail="Failed to update content session"
                )

        except Exception as e:
            self.logger.error(
                f"Error updating content session data in MongoDB: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def update_permissions_token_in_mongo(
        self, user_id: str, permissions_token_id: str, update_fields: dict[str, Any]
    ) -> None:
        try:
            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("permissions_tokens")
            result = await mongo_instance.update_one(
                {"userId": user_id, "_id": permissions_token_id},
                {"$set": update_fields},
            )
            if result.matched_count:
                self.logger.info(
                    f"Updated permissions token with ID {permissions_token_id} for user {user_id}"
                )
            else:
                self.logger.info(
                    f"No permissions token found to update with ID {permissions_token_id} for user {user_id}"
                )
                raise HTTPException(
                    status_code=404, detail="Permissions token not found"
                )
        except Exception as e:
            self.logger.error(
                f"Error updating permissions token data in MongoDB: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def update_user_in_mongo(
        self, user_id: str, update_fields: dict[str, Any]
    ) -> str | None:
        try:
            update_fields["lastUpdated"] = datetime.now(UTC).isoformat()

            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("users")
            result = await mongo_instance.update_one(
                {"_id": user_id}, {"$set": update_fields}
            )
            if result.matched_count:
                return user_id
            else:
                self.logger.info(f"No user found to update with user ID: {user_id}")
                raise HTTPException(status_code=404, detail="User not found")
        except Exception as e:
            self.logger.error(
                f"Error updating user data: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def update_notification_as_seen_in_mongo(
        self, user_id: str, notification_id: str, seen_at: datetime
    ) -> dict[str, Any]:
        try:
            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("notifications")

            # Calculate expiration date (1 day from seen_at)
            expiration_date = seen_at + timedelta(days=1)

            # Update the notification
            result = await mongo_instance.find_one_and_update(
                {"userId": user_id, "_id": notification_id},
                {
                    "$set": {
                        "seen": True,
                        "seenAt": seen_at,
                        "expiresAt": expiration_date,
                    }
                },
                return_document=True,  # Return the updated document
            )

            if result:
                self.logger.debug(
                    f"Notification with ID {notification_id} updated successfully."
                )
                # Convert ObjectId to string for consistency with Redis
                result["_id"] = str(result["_id"])
                return result
            else:
                self.logger.error(
                    f"No notification found with ID {notification_id} for user {user_id}."
                )
                raise HTTPException(status_code=404, detail="Notification not found")
        except Exception as e:
            self.logger.error(
                f"Error marking notification as seen in MongoDB: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    # Delete operations
    async def delete_content_session_in_mongo(
        self, user_id: str, content_session_id: str
    ) -> None:
        try:
            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("content_sessions")
            result = await mongo_instance.delete_one(
                {"userId": user_id, "_id": content_session_id}
            )

            if result.deleted_count:
                self.logger.info(
                    f"Deleted content session with ID {content_session_id} for user {user_id}"
                )
            else:
                self.logger.info(
                    f"No content session found to delete with ID {content_session_id} for user {user_id}"
                )
                raise HTTPException(status_code=404, detail="Content session not found")
        except Exception as e:
            self.logger.error(
                f"Error deleting content session from MongoDB: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def delete_user_from_mongo(self, user_id: str) -> None:
        try:
            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("users")
            result = await mongo_instance.delete_one({"_id": user_id})
            if result.deleted_count:
                self.logger.info(f"Deleted user with user ID {user_id}")
            else:
                self.logger.info(f"No user found to delete with user ID: {user_id}")
                raise HTTPException(status_code=404, detail="User not found")
        except Exception as e:
            self.logger.error(f"Error deleting user: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    async def delete_permissions_token_from_mongo(
        self, permissions_token_id: str
    ) -> None:
        try:
            mongo_instance = self.mongo_client.get_database(
                self.secrets["mongo_db_name"]
            ).get_collection("permissions_tokens")
            result = await mongo_instance.delete_one({"_id": permissions_token_id})
            if result.deleted_count:
                self.logger.info(
                    f"Deleted permissions token with ID {permissions_token_id}"
                )
            else:
                self.logger.info(
                    f"No permissions token found to delete with ID: {permissions_token_id}"
                )
                raise HTTPException(
                    status_code=404, detail="Permissions token not found"
                )
        except Exception as e:
            self.logger.error(
                f"Error deleting permissions token: {e}\n{traceback.format_exc()}"
            )
            raise HTTPException(status_code=500, detail="Internal Server Error")
