from datetime import datetime, date
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

from app.models.daily_plan import DailyPlanStatus
from app.schemas.daily_reflection import DailyReflectionCreate
from app.schemas.daily_task import DailyTaskResponse


class DailyPlanCreate(BaseModel):
    date: date
    notes: Optional[str] = None


class DailyPlanUpdate(BaseModel):
    notes: Optional[str] = None
    status: Optional[DailyPlanStatus] = None


class DailyPlanResponse(BaseModel):
    id: UUID
    date: date
    status: DailyPlanStatus
    notes: Optional[str]
    tasks: List[DailyTaskResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class DailyPlanCloseRequest(BaseModel):
    reflection: Optional[DailyReflectionCreate] = None
