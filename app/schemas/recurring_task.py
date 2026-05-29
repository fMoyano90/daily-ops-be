from datetime import datetime, time
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

from app.models.recurring_task import RecurringTaskType, RecurringInstanceStatus
from app.models.task import Priority
from app.schemas.project import ProjectResponse
from app.schemas.url_validation import normalize_external_url


class RecurringTaskCreate(BaseModel):
    project_id: UUID
    title: str
    description: Optional[str] = None
    priority: Priority = Priority.medium
    estimated_seconds: Optional[int] = Field(default=None, ge=0)
    category: Optional[str] = None
    meeting_time: Optional[time] = None
    external_url: Optional[str] = None
    tag: Optional[str] = None
    recurrence_type: RecurringTaskType
    recurrence_days: Optional[List[int]] = None
    reminder_minutes_before: Optional[int] = Field(default=None, ge=0)

    @field_validator("external_url")
    @classmethod
    def validate_external_url(cls, value: Optional[str]) -> Optional[str]:
        return normalize_external_url(value)


class RecurringTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[Priority] = None
    estimated_seconds: Optional[int] = Field(default=None, ge=0)
    category: Optional[str] = None
    meeting_time: Optional[time] = None
    external_url: Optional[str] = None
    tag: Optional[str] = None
    project_id: Optional[UUID] = None
    recurrence_type: Optional[RecurringTaskType] = None
    recurrence_days: Optional[List[int]] = None
    is_active: Optional[bool] = None
    reminder_minutes_before: Optional[int] = Field(default=None, ge=0)

    @field_validator("external_url")
    @classmethod
    def validate_external_url(cls, value: Optional[str]) -> Optional[str]:
        return normalize_external_url(value)


class RecurringInstanceResponse(BaseModel):
    id: UUID
    recurring_task_id: UUID
    date: datetime
    daily_task_id: Optional[UUID] = None
    status: RecurringInstanceStatus
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RecurringTaskResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    description: Optional[str]
    priority: Priority
    estimated_seconds: Optional[int] = None
    category: Optional[str]
    meeting_time: Optional[time] = None
    external_url: Optional[str] = None
    tag: Optional[str] = None
    recurrence_type: RecurringTaskType
    recurrence_days: Optional[List[int]]
    is_active: bool
    reminder_minutes_before: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    project: Optional[ProjectResponse] = None
    instances_count: int = 0
    completed_count: int = 0

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_stats(cls, obj, instances_count: int = 0, completed_count: int = 0):
        data = cls.model_validate(obj)
        data.instances_count = instances_count
        data.completed_count = completed_count
        return data
