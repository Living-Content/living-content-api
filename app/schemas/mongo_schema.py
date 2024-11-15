# app/schemas/mongo_schema.py
import inflection


async def generate_user_data(
    user_id,
    access_token,
    permissions_token,
    created_at,
    auth_provider=None,
    auth_user_id=None,
):
    """
    Generates a user data dictionary.

    Args:
        user_id (str): The user ID.
        access_token_id (str): The access token ID.
        permissions_token_id (str): The permissions token ID.
        created_at (datetime): The timestamp when the user was created.
        auth_provider (str, optional): The authentication provider.
        auth_user_id (str, optional): The user ID from the authentication provider.

    Returns:
        dict: The user data dictionary.
    """
    user_data = {
        "_id": user_id,  # Using _id for MongoDB's primary index
        "accessToken": access_token,  # Reference to the access token
        "permissionsToken": permissions_token,  # Reference to the permissions token
        "activeContentSessionId": None,  # Reference to the active content session
        "createdAt": created_at,
        "lastAccessed": created_at,
        "lastUpdated": created_at,
        "requests": {"allTime": 0},
        "unreadNotifications": {},
        "authProviders": {},
        "verified": False,
        "emailAddress": None,
        "password": None,
        "locked": False,
    }

    # Optionally add auth provider information if provided
    if auth_provider and auth_user_id:
        camel_case_provider = inflection.camelize(auth_provider, False)
        user_data["authProviders"][camel_case_provider] = auth_user_id

    return user_data


async def generate_permissions_token_data(user_id, permissions_token, created_at):
    """
    Generates a permissions token data dictionary.

    Args:
        permissions_token_id (str): The ID for the permissions token.
        user_id (str): The ID of the user to whom the token belongs.
        created_at (datetime): The timestamp when the permissions token was created.

    Returns:
        dict: The permissions token data dictionary.
    """
    return {
        "_id": permissions_token,  # Unique identifier for the permissions token
        "userId": user_id,  # Universal user ID
        "createdAt": created_at,
        "permissions": {"role": "user"},
    }


async def generate_content_session_data(
    user_id: str, content_session_id: str, created_at: str
):
    """
    Generates a content session data dictionary.

    Args:
        user_id (str): The ID of the user who created the content session.
        content_session_id (str): The ID of the content session.
        created_at (str): The timestamp when the content session was created.

    Returns:
        dict: The content session data dictionary.
    """
    return {
        "_id": content_session_id,
        "userId": user_id,
        "createdAt": created_at,
        "lastUpdated": created_at,
        "name": None,
        "sessionData": {},
    }


async def generate_notification_data(
    notification_id: str,
    user_id: str,
    content_session_id: str,
    created_at: str,
    associated_message_id: str = None,
    associated_task_id: str = None,
    associated_message: str = None,
    associated_image: str = None,
    toast_type: str = "text",
    toast_message: str = None,
    style: str = "normal",
    persistent: bool = False,
    seen: bool = False,
    seen_at: str = None,
    response_data: dict = None,
):
    """
    Generates a notification data dictionary.

    Args:
        notification_id (str): The ID of the notification.
        user_id (str): The ID of the user who received the notification.
        content_session_id (str): The ID of the content session associated with the notification.
        associated_message_id (str): The ID of the message associated with the notification.
        associated_task_id (str): The ID of the task associated with the notification
        created_at (str): The timestamp when the notification was created.
        type (str): The type of the notification.
        toast_message (str): The message to be displayed as a toast notification.
        associated_message (str): The message associated with the notification.
        associated_image (str): The URL of the image associated with the notification.
        style (str): The style of the notification.
        persistent (bool): Whether the notification is persistent.
        seen (bool): Whether the notification has been seen.
        seen_at (str): The timestamp when the notification was seen.
        response_data (dict): Additional response data related to the notification.

    Returns:
        dict: The notification data dictionary.
    """
    return {
        "_id": notification_id,
        "userId": user_id,
        "contentSessionId": content_session_id,
        "associatedMessageId": associated_message_id,
        "associatedTaskId": associated_task_id,
        "associatedImage": associated_image,
        "createdAt": created_at,
        "toastType": toast_type,
        "toastMessage": toast_message,
        "associatedMessage": associated_message,
        "style": style,
        "persistent": persistent,
        "seen": seen,
        "seenAt": seen_at,
        "responseData": response_data if response_data is not None else {},
    }
