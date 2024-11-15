# app/routers/health.py

from fastapi import APIRouter
from starlette.status import HTTP_200_OK
import logging

router = APIRouter(tags=["Healthz"])


@router.get(
    "/healthz",
    status_code=HTTP_200_OK,
    summary="Health Check",
    response_description="Health Status",
)
async def healthz():
    logging.getLogger("healthz").info("Health check endpoint called")
    return {
        "status": "running",
        "message": "Service is (probably) healthy. Well; at least this endpoint works.",
    }
