# app/models/websocket.py

from pydantic import BaseModel, Field


class BaseWebSocketMessage(BaseModel):
    type: str


class UpdateNotificationAsSeenMessage(BaseWebSocketMessage):
    notification_id: str = Field(..., alias="notificationId")
    content_session_id: str = Field(..., alias="contentSessionId")

    class Config:
        populate_by_name = True


class UpdateUnreadMessagesMessage(BaseWebSocketMessage):
    unread_message_status: bool = Field(..., alias="unreadMessageStatus")
    content_session_id: str = Field(..., alias="contentSessionId")

    class Config:
        populate_by_name = True
