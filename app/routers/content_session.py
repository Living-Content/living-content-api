from fastapi import APIRouter, Depends, HTTPException, Request, status, Header
from app.lib.content_session_manager import ContentSessionManager
from app.lib.dependencies import get_content_session_manager
from app.models.content_session import UpdateContentSessionData

router = APIRouter(tags=["Content Session"])

# Routes


@router.post("/content-session/create")
async def create_content_session(
    request: Request,
    content_session_manager: ContentSessionManager = Depends(
        get_content_session_manager
    ),
):
    try:
        # Access normalized user_id and access_token from request.state
        user_id = request.state.user_id
        access_token = request.state.access_token

        if not user_id or not access_token:
            raise HTTPException(status_code=403, detail="Unauthorized access")

        content_session_data = await content_session_manager.create_content_session(
            user_id
        )
        return {
            "status": "success",
            "message": "Content Session created successfully",
            "data": content_session_data,
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Internal server error",
                "data": "internal_server_error",
                "details": str(e),
            },
        )


@router.get("/content-session/get")
async def get_content_session(
    request: Request,
    content_session_manager: ContentSessionManager = Depends(
        get_content_session_manager
    ),
    content_session_id: str = Header(None, alias="X-Content-Session-ID"),
):
    try:
        user_id = request.state.user_id
        access_token = request.state.access_token

        if not user_id or not access_token:
            raise HTTPException(status_code=403, detail="Unauthorized access")

        content_session = await content_session_manager.get_content_session(
            user_id, content_session_id
        )
        if not content_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": "Content Session not found",
                    "data": "no_content_session",
                },
            )
        return {
            "status": "success",
            "data": content_session,
            "message": "Content Session retrieved successfully",
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Internal server error",
                "data": "internal_server_error",
                "details": str(e),
            },
        )


@router.get("/content-session/get-data")
async def get_content_session_data(
    request: Request,
    content_session_manager: ContentSessionManager = Depends(
        get_content_session_manager
    ),
    content_session_id: str = Header(None, alias="X-Content-Session-ID"),
):
    try:
        user_id = request.state.user_id
        access_token = request.state.access_token

        if not user_id or not access_token:
            raise HTTPException(status_code=403, detail="Unauthorized access")

        content_session_data = await content_session_manager.get_content_session_data(
            user_id, content_session_id
        )
        return {
            "status": "success",
            "data": {"sessionData": content_session_data},
            "message": "Content Session retrieved successfully",
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Internal server error",
                "data": "internal_server_error",
                "details": str(e),
            },
        )


@router.put("/content-session/update")
async def update_content_session(
    request: Request,
    update_data: UpdateContentSessionData,
    content_session_manager: ContentSessionManager = Depends(
        get_content_session_manager
    ),
    content_session_id: str = Header(None, alias="X-Content-Session-ID"),
):
    try:
        user_id = request.state.user_id
        access_token = request.state.access_token

        if not user_id or not access_token:
            raise HTTPException(status_code=403, detail="Unauthorized access")

        if not content_session_id or not update_data.new_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": "Content Session not found",
                    "data": "no_content_session",
                },
            )

        existing_content_session = await content_session_manager.get_content_session(
            user_id, content_session_id
        )
        if not existing_content_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": "Content Session not found",
                    "data": "no_content_session",
                },
            )

        await content_session_manager.update_content_session(
            user_id, content_session_id, update_data.new_data
        )
        return {
            "status": "success",
            "data": "content_session_updated",
            "message": "Content Session updated successfully",
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Internal server error",
                "data": "internal_server_error",
                "details": str(e),
            },
        )
