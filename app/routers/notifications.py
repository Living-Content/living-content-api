from fastapi import APIRouter, Depends, HTTPException, Request
from app.models.notification import GetUnseenNotificationsRequest
from app.lib.dependencies import get_http_notification_manager
from app.lib.notification_manager import NotificationManager
import logging

router = APIRouter(tags=["Notifications"])


@router.put("/notifications/get-unseen")
async def get_unseen_notifications(
    request: Request,
    notification_manager: NotificationManager = Depends(get_http_notification_manager),
):
    try:
        # Access normalized user_id and access_token from request.state
        user_id = request.state.user_id
        access_token = request.state.access_token
        content_session_id = request.headers.get("X-Content-Session-ID")

        if not user_id or not access_token:
            raise HTTPException(status_code=403, detail="Unauthorized access")

        if not content_session_id:
            raise HTTPException(status_code=403, detail="Content session ID not found")

        # Fetch unseen notifications
        notifications = await notification_manager.get_unseen_notifications(
            user_id, str(content_session_id)
        )
        return {
            "status": "success",
            "data": {"notifications": notifications},
            "message": "Unseen notifications retrieved successfully",
        }

    except ValueError as e:
        logging.error(f"Value error in get_unseen_notifications: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e:
        logging.error(
            f"HTTP Exception in get_unseen_notifications: {e.status_code}: {e.detail}"
        )
        raise e
    except Exception as e:
        logging.error(f"Unexpected error in get_unseen_notifications: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
