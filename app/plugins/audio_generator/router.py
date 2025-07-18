from fastapi import APIRouter, Depends, HTTPException
from starlette.status import HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR

from app.plugins.audio_generator.dependencies import get_audio_generator_functions
from app.plugins.audio_generator.functions import AudioGeneratorFunctions

router = APIRouter(tags=["audio_generator"])


@router.get(
    "/audio-generator/jenai/status",
    status_code=HTTP_200_OK,
    response_model=dict,  # Update this if you have a response model defined
)
async def jenai_status(
    id: str,
    audio_generator_functions: AudioGeneratorFunctions = Depends(
        get_audio_generator_functions
    ),
):
    try:
        # Attempt to call the request handler function
        response = (
            await audio_generator_functions.jenai_request_handler.get_jenai_status(
                f"/api/v1/public/generation_status/{id}"
            )
        )

        # If response contains an error status, raise an HTTPException
        if response.get("status") == "error":
            raise HTTPException(
                status_code=response.get("status_code", HTTP_500_INTERNAL_SERVER_ERROR),
                detail=response.get("message", "Unknown error occurred"),
            )

        return response

    except HTTPException as http_exc:
        # Re-raise HTTP exceptions to propagate them to the client
        raise http_exc

    except Exception as exc:
        # Handle any other exceptions and log if necessary
        error_message = f"An unexpected error occurred: {exc!s}"
        print(error_message)  # Replace with logging if available
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=error_message
        )
