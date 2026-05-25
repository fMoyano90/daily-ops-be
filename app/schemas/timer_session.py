from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class TimerSessionResponse(BaseModel):
    id: UUID
    daily_task_id: UUID
    started_at: datetime
    stopped_at: datetime | None
    duration_seconds: int

    model_config = {"from_attributes": True}


class TimerStartResponse(BaseModel):
    session_id: UUID
    started_at: datetime


class TimerStopResponse(BaseModel):
    session_id: UUID
    stopped_at: datetime
    duration_seconds: int
    task_total_seconds: int
