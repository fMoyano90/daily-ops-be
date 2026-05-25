from uuid import UUID
from pydantic import BaseModel

from app.models.daily_subtask import SubtaskStatus
from app.models.task import Priority


class DailySubtaskCreate(BaseModel):
    title: str
    priority: Priority = Priority.medium


class DailySubtaskUpdate(BaseModel):
    title: str = None
    status: SubtaskStatus = None
    priority: Priority = None
    sort_order: int = None


class DailySubtaskResponse(BaseModel):
    id: UUID
    daily_task_id: UUID
    title: str
    status: SubtaskStatus
    priority: Priority
    sort_order: int

    model_config = {"from_attributes": True}
