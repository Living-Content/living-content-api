# app/models/notification.py

from pydantic import BaseModel, Field
from typing import Optional, Dict
from uuid import UUID
from datetime import datetime


class Notification(BaseModel):
    id: str = Field(alias="_id")
    user_id: str = Field(alias="userId")
    content_session_id: Optional[str] = Field(alias="contentSessionId")
    created_at: datetime = Field(alias="createdAt")
    type: str
    toast: str
    style: str
    emit: Optional[str]
    persistent: bool
    seen: bool
    seen_at: Optional[datetime] = Field(alias="seenAt")
    notifcationData: Optional[Dict] = {}


class GetUnseenNotificationsRequest(BaseModel):
    content_session_id: UUID = Field(alias="contentSessionId")
