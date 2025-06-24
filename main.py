import os
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette import status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Import routers
from app.routers import (
    function,
    health,
    query,
    websocket,
    content_session,
    webhook,
    user,
    access_token,
    permissions_token,
    notifications,
)

# Import custom modules and managers
from app.lib.config import ConfigSingleton
from app.lib.secrets import SecretsSingleton
from app.lib.connection_manager import ConnectionManager
from app.lib.content_session_manager import ContentSessionManager
from app.lib.notification_manager import NotificationManager
from app.lib.websocket_manager import WebSocketManager
from app.lib.user_manager import UserManager
from app.lib.permissions_token_manager import PermissionsTokenManager
from app.middleware.access_token_middleware import AccessTokenMiddleware
from app.middleware.custom_cors_middleware import CustomCORSMiddleware
from app.lib.logging_config import setup_logging


def include_all_plugin_routers(app: FastAPI, config: dict):
    """Include all enabled plugin routers."""
    for plugin_name, plugin_config in config["plugins"].items():
        if plugin_config.get("enabled", False):
            try:
                module = __import__(
                    f"app.plugins.{plugin_name}.router", fromlist=["router"]
                )
                router = getattr(module, "router")
                app.include_router(router, tags=[plugin_name])
                logging.info(f"Plugin '{plugin_name}' router included")
            except Exception as e:
                logging.error(f"Failed to load plugin {plugin_name}: {e}")


def setup_eqty_sdk():
    """Set up the Eqty SDK if available."""
    try:
        import eqty

        current_file_path = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file_path)
        sdk_dir = os.path.join(current_dir, "eqty-sdk")

        logging.info("Setting up Eqty SDK")
        eqty.init(
            project="living-content",
            did_key_name="living-content-key",
            custom_dir=sdk_dir,
        )
        logging.info("Eqty SDK setup complete")
    except ImportError as e:
        logging.warning(f"Failed to import eqty: {e}")
    except Exception as e:
        logging.error(f"Unexpected error during eqty SDK setup: {e}")


async def initialize_managers(app: FastAPI):
    """Initialize all application managers in the correct dependency order."""
    try:
        connection_manager = app.state.connection_manager
        config = app.state.config
        secrets = app.state.secrets

        # Get base clients
        mongo_client = await connection_manager.get_mongo_client()
        redis_client = await connection_manager.get_redis_client()
        websocket_client = await connection_manager.get_websocket_client()

        # Initialize managers in dependency order
        app.state.permissions_token_manager = PermissionsTokenManager(mongo_client)
        logging.info("PermissionsTokenManager initialized")

        app.state.content_session_manager = ContentSessionManager(
            mongo_client, redis_client
        )
        logging.info("ContentSessionManager initialized")

        app.state.notification_manager = NotificationManager(
            mongo_client, redis_client, websocket_client
        )
        logging.info("NotificationManager initialized")

        # Initialize WebSocket manager after its dependencies
        app.state.websocket_manager = WebSocketManager(
            connection_manager,
            app.state.notification_manager,
        )
        # Start the WebSocket cleanup listener for worker coordination
        asyncio.create_task(app.state.websocket_manager.start_cleanup_listener())
        logging.info("WebSocketManager initialized")

        app.state.user_manager = UserManager(
            app.state.content_session_manager,
            app.state.permissions_token_manager,
            mongo_client,
            redis_client,
            config,
            secrets,
        )
        logging.info("UserManager initialized")

    except Exception as e:
        logging.error(f"Error initializing managers: {e}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    setup_logging()
    logging.info("Starting up the application")

    try:
        # Initialize configuration
        allowed_config_files = [
            "clients",
            "deployment",
            "eqty",
            "ingress",
            "internal_functions",
            "persona",
            "plugins",
            "project",
        ]
        config = await ConfigSingleton.initialize(allowed_config_files)
        app.state.config = config
        logging.info("Configuration initialized")

        # Initialize secrets
        app.state.secrets = await SecretsSingleton.initialize()
        logging.info("Secrets initialized")

        # Initialize connection manager
        logging.info("Initializing ConnectionManager")
        connection_manager = await ConnectionManager.create(app)
        app.state.connection_manager = connection_manager
        logging.info("ConnectionManager initialized")

        # Initialize all other managers
        await initialize_managers(app)

        # Setup additional components
        setup_eqty_sdk()

        # Register app routes
        routers = [
            health,
            websocket,
            content_session,
            webhook,
            user,
            access_token,
            permissions_token,
            query,
            function,
            notifications,
        ]
        for router in routers:
            app.include_router(router.router)
            logging.debug(f"Router {router.__name__} included")

        # Include plugin routers
        include_all_plugin_routers(app, config)

        logging.info("Application initialization complete")
    except Exception as e:
        logging.error(f"Critical error during application initialization: {e}")
        raise

    yield

    # Shutdown
    logging.info("Starting application shutdown")
    try:
        if hasattr(app.state, "connection_manager"):
            await app.state.connection_manager.close_clients()
            logging.info("Connection manager closed successfully")
    except Exception as e:
        logging.error(f"Error during application shutdown: {e}")
    finally:
        logging.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(lifespan=lifespan)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with custom format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": (
                exc.detail["message"]
                if isinstance(exc.detail, dict) and "message" in exc.detail
                else str(exc.detail)
            ),
            "data": (
                exc.detail["data"]
                if isinstance(exc.detail, dict) and "data" in exc.detail
                else "error"
            ),
            "details": (
                exc.detail["details"]
                if isinstance(exc.detail, dict) and "details" in exc.detail
                else None
            ),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Validation error",
            "data": "validation_error",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def custom_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions."""
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "Internal server error",
            "data": "internal_server_error",
            "details": str(exc),
        },
    )


# Add middleware
app.add_middleware(CustomCORSMiddleware)
app.add_middleware(AccessTokenMiddleware)
