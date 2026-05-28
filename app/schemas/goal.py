from datetime import datetime, date
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.goal import GoalHorizon, GoalStatus, GoalStepStatus


class GoalStepCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    sort_order: int = 0
    linked_task_id: Optional[UUID] = None
    due_date: Optional[date] = None


class GoalStepUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[GoalStepStatus] = None
    sort_order: Optional[int] = None
    due_date: Optional[date] = None


class GoalStepResponse(BaseModel):
    id: UUID
    goal_id: UUID
    title: str
    status: GoalStepStatus
    sort_order: int
    linked_task_id: Optional[UUID] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class GoalCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class GoalCommentUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class GoalCommentResponse(BaseModel):
    id: UUID
    goal_id: UUID
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GoalCreate(BaseModel):
    project_id: UUID
    title: str = Field(min_length=1, max_length=500)
    description: Optional[str] = None
    horizon: GoalHorizon = GoalHorizon.medium
    start_date: date
    target_date: date
    anti_goals: Optional[str] = None
    key_results: Optional[str] = None


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    horizon: Optional[GoalHorizon] = None
    status: Optional[GoalStatus] = None
    start_date: Optional[date] = None
    target_date: Optional[date] = None
    anti_goals: Optional[str] = None
    key_results: Optional[str] = None


class GoalResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    description: Optional[str] = None
    horizon: GoalHorizon
    status: GoalStatus
    progress: float
    start_date: date
    target_date: date
    completed_at: Optional[datetime] = None
    anti_goals: Optional[str] = None
    key_results: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    steps: list[GoalStepResponse] = []
    comments: list[GoalCommentResponse] = []
    linked_task_ids: list[UUID] = []

    model_config = {"from_attributes": True}


class GoalSummaryItem(BaseModel):
    count: int
    avg_progress: float
    nearest_deadline: Optional[str] = None
    nearest_goal_title: Optional[str] = None


class GoalSummaryResponse(BaseModel):
    short: GoalSummaryItem
    medium: GoalSummaryItem
    long: GoalSummaryItem
