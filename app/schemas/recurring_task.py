from datetime import datetime, time
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, field_validator

from app.models.recurring_task import RecurringTaskType, RecurringInstanceStatus
from app.models.task import Priority
from app.schemas.project import ProjectResponse
from app.schemas.url_validation import normalize_external_url


class RecurringTaskCreate(BaseModel):
    project_id: UUID
    title: str
    description: Optional[str] = None
    priority: Priority = Priority.medium
    category: Optional[str] = None
    meeting_time: Optional[time] = None
    external_url: Optional[str] = None
    tag: Optional[str] = None
    recurrence_type: RecurringTaskType
    recurrence_days: Optional[List[int]] = None

    @field_validator("external_url")
    @classmethod
    def validate_external_url(cls, value: Optional[str]) -> Optional[str]:
        return normalize_external_url(value)


class RecurringTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[Priority] = None
    category: Optional[str] = None
    meeting_time: Optional[time] = None
    external_url: Optional[str] = None
    tag: Optional[str] = None
    project_id: Optional[UUID] = None
    recurrence_type: Optional[RecurringTaskType] = None
    recurrence_days: Optional[List[int]] = None
    is_active: Optional[bool] = None

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
    category: Optional[str]
    meeting_time: Optional[time] = None
    external_url: Optional[str] = None
    tag: Optional[str] = None
    recurrence_type: RecurringTaskType
    recurrence_days: Optional[List[int]]
    is_active: bool
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
