# app/plugins/image_generator/dependencies.py

from fastapi import Request, Depends, WebSocket
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis
from typing import Any, Dict, Union

# Import custom modules
from app.lib.config import ConfigSingleton
from app.lib.secrets import SecretsSingleton
from app.lib.notification_manager import NotificationManager
from app.lib.user_manager import UserManager
from app.lib.content_session_manager import ContentSessionManager
from app.lib.permissions_token_manager import PermissionsTokenManager
from app.clients.openai_client import OpenAI_Client
from app.lib.connection_manager import ConnectionManager
from app.lib.websocket_manager import WebSocketManager
from app.clients.websocket_client import WebSocketClient
from app.lib.query_handler import QueryHandler
from app.lib.function_handler import FunctionHandler


# Dependency functions for configuration and secrets management
def get_config() -> Dict[str, Any]:
    """Retrieve the application configuration singleton.

    Returns:
        Dict[str, Any]: Application configuration dictionary containing settings
        like API endpoints, timeouts, and other operational parameters.
    """
    return ConfigSingleton.get_config()


def get_secrets() -> Dict[str, Any]:
    """Retrieve the application secrets singleton.

    Returns:
        Dict[str, Any]: Secure credentials dictionary containing sensitive data
        like API keys, tokens, and other security-related configurations.
    """
    return SecretsSingleton.get_secrets()


# Connection management dependencies
def get_connection_manager(context: Union[Request, WebSocket]) -> ConnectionManager:
    """Get the ConnectionManager from the FastAPI app state.
    This is a unified dependency that works with both HTTP requests and WebSocket connections.

    Args:
        context: Either a FastAPI Request or WebSocket object that contains the application state

    Returns:
        ConnectionManager: The application's connection manager instance that handles
        database connections, caching, and other persistent connections
    """
    return context.app.state.connection_manager


def get_ws_connection_manager(websocket: WebSocket) -> ConnectionManager:
    """WebSocket-specific dependency for connection management.

    Args:
        websocket: The WebSocket connection object

    Returns:
        ConnectionManager: Connection manager instance for WebSocket contexts
    """
    return websocket.app.state.connection_manager


def get_http_connection_manager(request: Request) -> ConnectionManager:
    """HTTP-specific dependency for connection management.

    Args:
        request: The HTTP request object

    Returns:
        ConnectionManager: Connection manager instance for HTTP contexts
    """
    return request.app.state.connection_manager


# Client dependencies
def get_websocket_client() -> WebSocketClient:
    """Create and return a new WebSocket client instance.

    Returns:
        WebSocketClient: A fresh instance of the WebSocket client for real-time communication
    """
    return WebSocketClient()


def get_openai_client() -> OpenAI_Client:
    """Create and return an OpenAI client configured with application settings.

    Returns:
        OpenAI_Client: Configured OpenAI client instance using app config and secrets
    """
    config = get_config()
    secrets = get_secrets()
    return OpenAI_Client(config, secrets)


# Notification management dependencies
def get_notification_manager(
    connection_manager: ConnectionManager = Depends(get_connection_manager),
) -> NotificationManager:
    """Unified dependency for notification management across both HTTP and WebSocket contexts.

    Args:
        connection_manager: The application's connection manager instance

    Returns:
        NotificationManager: Manager instance for handling system notifications
    """
    return connection_manager.app.state.notification_manager


def get_http_notification_manager(request: Request) -> NotificationManager:
    """HTTP-specific notification manager dependency.

    Args:
        request: The HTTP request object

    Returns:
        NotificationManager: Notification manager instance for HTTP contexts
    """
    return request.app.state.notification_manager


def get_ws_notification_manager(websocket: WebSocket) -> NotificationManager:
    """WebSocket-specific notification manager dependency.

    Args:
        websocket: The WebSocket connection object

    Returns:
        NotificationManager: Notification manager instance for WebSocket contexts
    """
    return websocket.app.state.notification_manager


def get_websocket_manager(websocket: WebSocket) -> WebSocketManager:
    """Create a WebSocket manager with required dependencies.

    Args:
        websocket: The WebSocket connection object

    Returns:
        WebSocketManager: Manager instance for handling WebSocket connections
    """
    connection_manager = get_ws_connection_manager(websocket)
    notification_manager = get_ws_notification_manager(websocket)
    return WebSocketManager(connection_manager, notification_manager)


# Database client dependencies
async def get_mongo_client(request: Request) -> AsyncIOMotorClient:
    """Get an async MongoDB client instance.

    Args:
        request: The HTTP request object

    Returns:
        AsyncIOMotorClient: Async MongoDB client for database operations
    """
    connection_manager = get_connection_manager(request)
    return await connection_manager.get_mongo_client()


async def get_redis_client(request: Request) -> redis.Redis:
    """Get an async Redis client instance.

    Args:
        request: The HTTP request object

    Returns:
        redis.Redis: Async Redis client for caching operations
    """
    connection_manager = get_connection_manager(request)
    return await connection_manager.get_redis_client()


# Application service dependencies
def get_content_session_manager(request: Request) -> ContentSessionManager:
    """Get the content session manager for handling user content sessions.

    Args:
        request: The HTTP request object

    Returns:
        ContentSessionManager: Manager for handling content sessions
    """
    return request.app.state.content_session_manager


def get_permissions_token_manager(request: Request) -> PermissionsTokenManager:
    """Get the permissions token manager for handling access control.

    Args:
        request: The HTTP request object

    Returns:
        PermissionsTokenManager: Manager for handling permissions and tokens
    """
    return request.app.state.permissions_token_manager


def get_user_manager(request: Request) -> UserManager:
    """Get the user manager for handling user-related operations.

    Args:
        request: The HTTP request object

    Returns:
        UserManager: Manager for user-related operations
    """
    return request.app.state.user_manager


# Handler dependencies
async def get_function_handler(
    config: dict = Depends(get_config),
    secrets: dict = Depends(get_secrets),
    content_session_manager: ContentSessionManager = Depends(
        get_content_session_manager
    ),
    notification_manager: NotificationManager = Depends(get_http_notification_manager),
) -> FunctionHandler:
    """Create a function handler with all required dependencies.

    Args:
        config: Application configuration dictionary
        secrets: Application secrets dictionary
        content_session_manager: Manager for content sessions
        notification_manager: Manager for notifications

    Returns:
        FunctionHandler: Handler for processing function calls
    """
    return FunctionHandler(
        config, secrets, content_session_manager, notification_manager
    )


async def get_query_handler(
    config: dict = Depends(get_config),
    secrets: dict = Depends(get_secrets),
    content_session_manager: ContentSessionManager = Depends(
        get_content_session_manager
    ),
    function_handler: FunctionHandler = Depends(get_function_handler),
) -> QueryHandler:
    """Create a query handler with all required dependencies.

    Args:
        config: Application configuration dictionary
        secrets: Application secrets dictionary
        content_session_manager: Manager for content sessions
        function_handler: Handler for function calls

    Returns:
        QueryHandler: Handler for processing queries
    """
    return QueryHandler(config, secrets, content_session_manager, function_handler)
