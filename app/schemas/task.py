from datetime import datetime, date, time
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, field_validator

from app.models.task import TaskSource, TaskStatus, Priority
from app.schemas.url_validation import normalize_external_url


class TaskCreate(BaseModel):
    project_id: UUID
    title: str
    description: Optional[str] = None
    source: TaskSource = TaskSource.manual
    external_key: Optional[str] = None
    external_url: Optional[str] = None
    priority: Priority = Priority.medium
    due_date: Optional[date] = None
    category: Optional[str] = None
    meeting_time: Optional[time] = None

    @field_validator("external_url")
    @classmethod
    def validate_external_url(cls, value: Optional[str]) -> Optional[str]:
        return normalize_external_url(value)


class TaskUpdate(BaseModel):
    project_id: Optional[UUID] = None
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[Priority] = None
    due_date: Optional[date] = None
    category: Optional[str] = None
    external_url: Optional[str] = None
    meeting_time: Optional[time] = None

    @field_validator("external_url")
    @classmethod
    def validate_external_url(cls, value: Optional[str]) -> Optional[str]:
        return normalize_external_url(value)


class TaskResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    description: Optional[str]
    source: TaskSource
    external_key: Optional[str]
    external_url: Optional[str]
    status: TaskStatus
    priority: Priority
    due_date: Optional[date]
    category: Optional[str]
    meeting_time: Optional[time] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
