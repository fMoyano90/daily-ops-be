from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class JiraConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    base_url: HttpUrl
    email: str = Field(..., min_length=3, max_length=255)
    api_token: str = Field(..., min_length=1)
    jql: Optional[str] = None
    project_color: Optional[str] = Field(default="#2563eb", max_length=7)


class JiraConnectionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    email: Optional[str] = Field(default=None, min_length=3, max_length=255)
    api_token: Optional[str] = None
    jql: Optional[str] = None
    enabled: Optional[bool] = None


class JiraConnectionResponse(BaseModel):
    id: UUID
    name: str
    base_url: str
    email: str
    jql: str
    project_id: UUID
    enabled: bool
    last_sync_at: Optional[datetime]
    last_sync_status: Optional[str]
    last_sync_error: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SyncResultResponse(BaseModel):
    connection_id: str
    connection_name: str
    created: int
    updated: int
    skipped: int
    errors: list[str]
    status: str


class JiraTestResponse(BaseModel):
    ok: bool
    account_id: Optional[str] = None
    display_name: Optional[str] = None
    email: Optional[str] = None
    error: Optional[str] = None
