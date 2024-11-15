from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging


class AccessTokenMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.logger = logging.getLogger(__name__)
        self.logger.debug("AccessTokenMiddleware initialized")
        self.excluded_paths = [
            "/access-token/user-creation-token/create",
            "/user/create",
            "/access-token/auth/regenerate",
            "/image-generator/apiframe/response",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/healthz",
            "/favicon.ico",
        ]

    async def dispatch(self, request: Request, call_next):
        # Get managers from app.state
        user_manager = request.app.state.user_manager
        config = request.app.state.config
        secrets = request.app.state.secrets

        allowed_origins = config["ingress"]["allowed_origins"]

        if request.url.path in self.excluded_paths:
            response = await call_next(request)
            self.add_cors_headers(request, response, allowed_origins)
            return response

        if request.method == "OPTIONS":
            return self.handle_cors_preflight(request, allowed_origins)

        user_id = request.headers.get("X-User-ID")
        auth_provider = request.headers.get("X-Auth-Provider")
        auth_provider_user_id = request.headers.get("X-Auth-User-ID")
        authorization = request.headers.get("Authorization")

        self.logger.debug(f"Request Headers: {request.headers}")

        if authorization and authorization.startswith("Bearer "):
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
        origin = request.headers.get("origin")
        if origin in allowed_origins:
            response.headers.update(
                {
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Credentials": "true",
                }
            )

    def invalid_access_token_response(self, request, allowed_origins):
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
