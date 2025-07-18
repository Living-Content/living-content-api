import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class AccessTokenMiddleware(BaseHTTPMiddleware):
    """
    Middleware for handling authentication and authorization in FastAPI applications.

    This middleware validates requests using either:
    1. A user access token authentication scheme
    2. An auth provider authentication scheme

    It also handles CORS (Cross-Origin Resource Sharing) headers and preflight requests.

    The middleware expects certain configuration and state to be present in the FastAPI app:
    - app.state.user_manager: Manager for user-related operations
    - app.state.config: Application configuration
    - app.state.secrets: Application secrets
    """

    def __init__(self, app):
        """
        Initialize the middleware.

        Args:
            app: The FastAPI application instance
        """
        super().__init__(app)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("AccessTokenMiddleware initialized")

    async def dispatch(self, request: Request, call_next):
        """
        Process incoming requests for authentication and authorization.

        Args:
            request (Request): The incoming request
            call_next: The next middleware or route handler in the chain

        Returns:
            Response: The response from the next handler or an error response

        Authentication can be performed in two ways:
        1. Using X-User-ID header with Bearer token
        2. Using X-Auth-Provider and X-Auth-User-ID headers with provider secret
        """
        # Get managers from app.state
        user_manager = request.app.state.user_manager
        config = request.app.state.config
        secrets = request.app.state.secrets

        allowed_origins = config["ingress"]["allowed_origins"]
        excluded_paths = config["ingress"]["excluded_paths"]

        # Skip authentication for excluded paths
        if request.url.path in excluded_paths:
            response = await call_next(request)
            self.add_cors_headers(request, response, allowed_origins)
            return response

        # Handle CORS preflight requests
        if request.method == "OPTIONS":
            return self.handle_cors_preflight(request, allowed_origins)

        # Extract authentication headers
        user_id = request.headers.get("X-User-ID")
        auth_provider = request.headers.get("X-Auth-Provider")
        auth_provider_user_id = request.headers.get("X-Auth-User-ID")
        authorization = request.headers.get("Authorization")

        self.logger.debug(f"Request Headers: {request.headers}")

        if authorization and authorization.startswith("Bearer "):
            # Handle user access token authentication
            if user_id:
                access_token = authorization.split(" ")[1]
                user = await user_manager.get_user_data(user_id)
                if user and user["accessToken"] == access_token:
                    request.state.user_id = user_id
                    request.state.access_token = access_token
                    response = await call_next(request)
                    self.add_cors_headers(request, response, allowed_origins)
                    return response
                return self.invalid_access_token_response(request, allowed_origins)

            # Handle auth provider authentication
            elif auth_provider_user_id and auth_provider:
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
                        self.logger.debug(
                            f"Auth provider: {request.state.auth_provider}"
                        )
                        self.logger.debug(f"User id: {request.state.user_id}")
                        self.logger.debug(f"Access token: {request.state.access_token}")
                        response = await call_next(request)
                        self.add_cors_headers(request, response, allowed_origins)
                        return response
                    return self.invalid_auth_provider_user(request, allowed_origins)
                return self.invalid_auth_provider_secret_response(
                    request, allowed_origins
                )

        # Case: Missing or invalid authorization
        return self.missing_authorization_response(request, allowed_origins)

    def handle_cors_preflight(self, request: Request, allowed_origins):
        """
        Handle CORS preflight requests.

        Args:
            request (Request): The incoming request
            allowed_origins (list): List of allowed origins

        Returns:
            JSONResponse: Response for the preflight request
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
        else:
            return JSONResponse(
                content={
                    "status": "error",
                    "data": "cors_policy_not_met",
                    "message": "CORS policy not met",
                },
                status_code=403,
            )

    def add_cors_headers(self, request: Request, response, allowed_origins):
        """
        Add CORS headers to the response if the origin is allowed.

        Args:
            request (Request): The incoming request
            response: The response object
            allowed_origins (list): List of allowed origins
        """
        origin = request.headers.get("origin")
        if origin in allowed_origins:
            response.headers.update(
                {
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Credentials": "true",
                }
            )

    def invalid_access_token_response(self, request, allowed_origins):
        """
        Generate response for invalid access token.

        Args:
            request (Request): The incoming request
            allowed_origins (list): List of allowed origins

        Returns:
            JSONResponse: Error response for invalid access token
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

    def invalid_auth_provider_user(self, request, allowed_origins):
        """
        Generate response for invalid auth provider user.

        Args:
            request (Request): The incoming request
            allowed_origins (list): List of allowed origins

        Returns:
            JSONResponse: Error response for invalid auth provider user
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

    def invalid_auth_provider_secret_response(self, request, allowed_origins):
        """
        Generate response for invalid auth provider secret.

        Args:
            request (Request): The incoming request
            allowed_origins (list): List of allowed origins

        Returns:
            JSONResponse: Error response for invalid auth provider secret
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

    def missing_authorization_response(self, request, allowed_origins):
        """
        Generate response for missing authorization headers.

        Args:
            request (Request): The incoming request
            allowed_origins (list): List of allowed origins

        Returns:
            JSONResponse: Error response for missing authorization headers
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
