# app/plugins/image_generator/router.py

from fastapi import APIRouter, Depends, HTTPException, Request, Response
import logging

# Local Plugin Imports
from models import ApiframeResponse
from dependencies import get_image_generator_functions
from functions import ImageGeneratorFunctions

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/image-generator/apiframe/response")
async def apiframe_response(
    response: ApiframeResponse,
    request: Request,
    image_generator_functions: ImageGeneratorFunctions = Depends(
        get_image_generator_functions
    ),
):
    logger.info(f"Received Apiframe response for task: {response.task_id}")
    logger.info(f"Response: {response}")

    headers = dict(request.headers)
    logger.info(f"All headers: {headers}")

    apiframe_response_handler = image_generator_functions.apiframe_response_handler

    try:
        task_data = await apiframe_response_handler.get_stored_task_data(
            response.task_id
        )

        await apiframe_response_handler.process_apiframe_response(response, task_data)

        return Response(status_code=200)

    except HTTPException as e:
        logger.error(f"HTTP exception in apiframe_response: {str(e)}")
        raise e

    except Exception as e:
        logger.error(f"Unexpected error in apiframe_response: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Error processing Apiframe response"
        )
