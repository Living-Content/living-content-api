# app/models/notification.py

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class Notification(BaseModel):
    id: str = Field(alias="_id")
    user_id: str = Field(alias="userId")
    content_session_id: str | None = Field(alias="contentSessionId")
    created_at: datetime = Field(alias="createdAt")
    type: str
    toast: str
    style: str
    emit: str | None
    persistent: bool
    seen: bool
    seen_at: datetime | None = Field(alias="seenAt")
    notifcationData: dict | None = {}


class GetUnseenNotificationsRequest(BaseModel):
    content_session_id: UUID = Field(alias="contentSessionId")
