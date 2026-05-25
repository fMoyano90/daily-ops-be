from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class TaskCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class TaskCommentUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class TaskCommentResponse(BaseModel):
    id: UUID
    task_id: Optional[UUID] = None
    recurring_task_id: Optional[UUID] = None
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
