from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionCreate(BaseModel):
    endpoint: str = Field(..., max_length=1000)
    keys: PushKeys
    user_agent: str | None = Field(default=None, max_length=500)


class PushSubscriptionResponse(BaseModel):
    id: UUID
    endpoint: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PushTestRequest(BaseModel):
    title: str = "DailyOps"
    body: str = "Notificación de prueba"
    url: str = "/today"
