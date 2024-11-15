from typing import Callable, Awaitable, List, Dict, Any
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
import logging


class AccessTokenMiddleware(BaseHTTPMiddleware):
    """
    Middleware for handling access token authentication and CORS in FastAPI applications.

    This middleware validates requests using either user access tokens or auth provider secrets.
    It handles CORS preflight requests and adds appropriate CORS headers to responses.
    Paths excluded from authentication are configured via ingress.excluded_paths config.

    Attributes:
        logger (logging.Logger): Logger instance for debugging and monitoring
        excluded_paths (List[str]): List of URL paths that bypass authentication, loaded from config

    Dependencies:
        - Requires a configured user_manager in app.state
        - Requires config with ingress.allowed_origins and ingress.excluded_paths in app.state
        - Requires secrets configuration in app.state
    """

    def __init__(self, app: Any) -> None:
        """
        Initialize the middleware with application and configuration.

        Args:
            app: The FastAPI application instance

        Note:
            Expects app.state.config to contain:
            {
                "ingress": {
                    "allowed_origins": List[str],
                    "excluded_paths": List[str]
                }
            }

            This is initially set in /config/ingress.yaml.
        """
        super().__init__(app)
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.debug("AccessTokenMiddleware initialized")

        # Load excluded paths from config during initialization
        self.excluded_paths: List[str] = []

        # We'll load the actual paths in the dispatch method since
        # app.state.config might not be available during initialization

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Process incoming requests for authentication and CORS handling.

        Args:
            request: The incoming HTTP request
            call_next: Callable to process the next middleware/route handler

        Returns:
            Response: The HTTP response, either from the next handler or an error response

        Authentication can succeed via two methods:
        1. User access token validation
        2. Auth provider secret validation
        """
        # Get managers and config from app.state
        user_manager = request.app.state.user_manager
        config = request.app.state.config
        secrets = request.app.state.secrets

        # Load configuration
        allowed_origins: List[str] = config["ingress"]["allowed_origins"]
        self.excluded_paths = config["ingress"]["excluded_paths"]

        if request.url.path in self.excluded_paths:
            response = await call_next(request)
            self.add_cors_headers(request, response, allowed_origins)
            return response

    # Auth handlers

    async def _handle_user_token_auth(
        self,
        request: Request,
        authorization: str,
        user_id: str,
        user_manager: Any,
        call_next: Callable[[Request], Awaitable[Response]],
        allowed_origins: List[str],
    ) -> Response:
        """
        Handle authentication using user access token.

        Args:
            request: The incoming HTTP request
            authorization: The Authorization header value
            user_id: The user ID from X-User-ID header
            user_manager: The user manager instance
            call_next: The next middleware/route handler
            allowed_origins: List of allowed CORS origins

        Returns:
            Response: Either the next handler's response or an error response
        """
        access_token = authorization.split(" ")[1]
        user = await user_manager.get_user_data(user_id)
        if user and user["accessToken"] == access_token:
            request.state.user_id = user_id
            request.state.access_token = access_token
            response = await call_next(request)
            self.add_cors_headers(request, response, allowed_origins)
            return response
        return self.invalid_access_token_response(request, allowed_origins)

    async def _handle_provider_auth(
        self,
        request: Request,
        authorization: str,
        auth_provider: str,
        auth_provider_user_id: str,
        user_manager: Any,
        secrets: Dict[str, str],
        call_next: Callable[[Request], Awaitable[Response]],
        allowed_origins: List[str],
    ) -> Response:
        """
        Handle authentication using auth provider secret.

        Args:
            request: The incoming HTTP request
            authorization: The Authorization header value
            auth_provider: The auth provider name
            auth_provider_user_id: The auth provider's user ID
            user_manager: The user manager instance
            secrets: The secrets configuration
            call_next: The next middleware/route handler
            allowed_origins: List of allowed CORS origins

        Returns:
            Response: Either the next handler's response or an error response
        """
        auth_provider_secret = authorization.split(" ")[1]
        auth_provider_key = f"auth-providers_{auth_provider}"

        if secrets.get(auth_provider_key) == auth_provider_secret:
            user = await user_manager.get_user_data_by_auth_provider(
                auth_provider, auth_provider_user_id
            )

            if user:
                request.state.auth_provider = user.get("authProvider")
                request.state.user_id = user.get("_id")
                request.state.access_token = user.get("accessToken")
                self.logger.debug(f"Auth provider: {request.state.auth_provider}")
                self.logger.debug(f"User id: {request.state.user_id}")
                self.logger.debug(f"Access token: {request.state.access_token}")
                response = await call_next(request)
                self.add_cors_headers(request, response, allowed_origins)
                return response
            return self.invalid_auth_provider_user(request, allowed_origins)
        return self.invalid_auth_provider_secret_response(request, allowed_origins)

    # CORS preflight

    def handle_cors_preflight(
        self, request: Request, allowed_origins: List[str]
    ) -> JSONResponse:
        """
        Handle CORS preflight (OPTIONS) requests.

        Args:
            request: The incoming HTTP request
            allowed_origins: List of allowed CORS origins

        Returns:
            JSONResponse: A response with appropriate CORS headers
        """
        origin = request.headers.get("origin")
        if origin in allowed_origins:
            response = JSONResponse(
                content={
                    "status": "success",
                    "data": "cors_preflight_ok",
                    "message": "CORS preflight OK",
                },
                status_code=200,
            )
            response.headers.update(
                {
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Methods": "OPTIONS, GET, POST, PUT, DELETE",
                    "Access-Control-Allow-Headers": "Authorization, Content-Type, X-User-ID, X-Content-Session-ID",
                    "Access-Control-Allow-Credentials": "true",
                }
            )
            return response
        return JSONResponse(
            content={
                "status": "error",
                "data": "cors_policy_not_met",
                "message": "CORS policy not met",
            },
            status_code=403,
        )

    def add_cors_headers(
        self, request: Request, response: Response, allowed_origins: List[str]
    ) -> None:
        """
        Add CORS headers to the response if origin is allowed.

        Args:
            request: The incoming HTTP request
            response: The response to add headers to
            allowed_origins: List of allowed CORS origins
        """
        origin = request.headers.get("origin")
        if origin in allowed_origins:
            response.headers.update(
                {
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Credentials": "true",
                }
            )

    # Error respones

    def invalid_access_token_response(
        self, request: Request, allowed_origins: List[str]
    ) -> JSONResponse:
        """
        Create response for invalid access token.

        Args:
            request: The incoming HTTP request
            allowed_origins: List of allowed CORS origins

        Returns:
            JSONResponse: Error response with CORS headers
        """
        self.logger.warning("Invalid access token.")
        response = JSONResponse(
            content={
                "status": "error",
                "data": "invalid_access_token",
                "message": "Invalid access token",
            },
            status_code=401,
        )
        self.add_cors_headers(request, response, allowed_origins)
        return response

    def invalid_auth_provider_user(
        self, request: Request, allowed_origins: List[str]
    ) -> JSONResponse:
        """
        Create response for invalid auth provider user.

        Args:
            request: The incoming HTTP request
            allowed_origins: List of allowed CORS origins

        Returns:
            JSONResponse: Error response with CORS headers
        """
        self.logger.warning("Invalid auth provider user.")
        response = JSONResponse(
            content={
                "status": "error",
                "data": "invalid_auth_provider_user",
                "message": "Invalid auth provider user",
            },
            status_code=401,
        )
        self.add_cors_headers(request, response, allowed_origins)
        return response

    def invalid_auth_provider_secret_response(
        self, request: Request, allowed_origins: List[str]
    ) -> JSONResponse:
        """
        Create response for invalid auth provider secret.

        Args:
            request: The incoming HTTP request
            allowed_origins: List of allowed CORS origins

        Returns:
            JSONResponse: Error response with CORS headers
        """
        self.logger.warning("Invalid auth provider secret.")
        response = JSONResponse(
            content={
                "status": "error",
                "data": "invalid_auth_provider_secret",
                "message": "Invalid auth provider secret",
            },
            status_code=401,
        )
        self.add_cors_headers(request, response, allowed_origins)
        return response

    def missing_authorization_response(
        self, request: Request, allowed_origins: List[str]
    ) -> JSONResponse:
        """
        Create response for missing authorization headers.

        Args:
            request: The incoming HTTP request
            allowed_origins: List of allowed CORS origins

        Returns:
            JSONResponse: Error response with CORS headers
        """
        self.logger.warning("Missing authorization headers.")
        response = JSONResponse(
            content={
                "status": "error",
                "data": "missing_authorization_headers",
                "message": "Missing authorization headers",
            },
            status_code=401,
        )
        self.add_cors_headers(request, response, allowed_origins)
        return response
