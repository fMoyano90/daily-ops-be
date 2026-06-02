from datetime import date as date_type, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CaptureCreate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    capture_type: Optional[str] = None
    source_url: Optional[str] = None
    tags: Optional[list[str]] = None
    note_date: Optional[date_type] = None


class CaptureUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    source_url: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None


class CaptureAttachmentResponse(BaseModel):
    id: UUID
    kind: str
    file_name: str
    mime_type: str
    size_bytes: int
    duration_seconds: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CaptureResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: Optional[str] = None
    content: Optional[str] = None
    capture_type: str
    source_url: Optional[str] = None
    status: str
    tags: list[str]
    note_date: date_type
    transcript: Optional[str] = None
    converted_task_id: Optional[UUID] = None
    attachments: list[CaptureAttachmentResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
