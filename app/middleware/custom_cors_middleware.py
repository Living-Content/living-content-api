import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CustomCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        config = request.app.state.config
        allowed_origins = config["ingress"]["allowed_origins"]

        origin = request.headers.get("origin")
        user_agent = request.headers.get("user-agent", "")
        api_token = request.headers.get("Authorization")
        webhook_secret = request.headers.get("x-webhook-secret")
        logging.debug(f"Handling CORS for origin: {origin}, User-Agent: {user_agent}")

        # Skip CORS check for internal health check and favicon requests
        if request.url.path == "/healthz" or request.url.path == "/favicon.ico":
            return await call_next(request)

        # Check if the request has a valid API token or x-webhook-secret (used for server-to-server authentication)
        if not origin and (api_token or webhook_secret):
            if api_token:
                logging.debug(
                    "No Origin header, but valid API token provided, allowing request"
                )
            if webhook_secret:
                logging.debug(
                    "No Origin header, but valid x-webhook-secret provided, allowing request"
                )
            return await call_next(request)

        # Basic check for non-browser clients
        is_non_browser = "curl" in user_agent.lower() or "postman" in user_agent.lower()

        # CORS checks for browser clients or clients with origin header
        if (
            origin
            and (origin in allowed_origins or "*" in allowed_origins)
            or is_non_browser
        ):
            if request.method == "OPTIONS":
                response = Response(status_code=204)
            else:
                response = await call_next(request)

            # Set specific CORS headers based on origin
            if origin and origin in allowed_origins:
                response.headers["Access-Control-Allow-Origin"] = origin
            else:
                response.headers["Access-Control-Allow-Origin"] = "*"

            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = (
                "OPTIONS, GET, POST, PUT, DELETE"
            )
            response.headers["Access-Control-Allow-Headers"] = (
                "Authorization, Content-Type, X-User-ID, X-Content-Session-ID, x-webhook-secret"
            )
        else:
            logging.warning(f"Origin not allowed: {origin}")
            response = Response(
                content='{"detail": "CORS origin not allowed"}',
                status_code=403,
                media_type="application/json",
            )

        return response
