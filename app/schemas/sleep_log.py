from datetime import date, datetime, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SleepLogCreate(BaseModel):
    date: Optional[date] = None
    hours_slept: Optional[float] = Field(default=None, ge=0, le=24)
    sleep_quality: Optional[int] = Field(default=None, ge=1, le=10)
    bedtime: Optional[time] = None
    wake_time: Optional[time] = None
    wakeups: Optional[int] = Field(default=None, ge=0, le=50)
    tiredness_on_wake: Optional[int] = Field(default=None, ge=1, le=10)
    tiredness_during_day: Optional[int] = Field(default=None, ge=1, le=10)
    note: Optional[str] = None


class SleepLogUpdate(BaseModel):
    hours_slept: Optional[float] = Field(default=None, ge=0, le=24)
    sleep_quality: Optional[int] = Field(default=None, ge=1, le=10)
    bedtime: Optional[time] = None
    wake_time: Optional[time] = None
    wakeups: Optional[int] = Field(default=None, ge=0, le=50)
    tiredness_on_wake: Optional[int] = Field(default=None, ge=1, le=10)
    tiredness_during_day: Optional[int] = Field(default=None, ge=1, le=10)
    note: Optional[str] = None


class SleepLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    daily_plan_id: Optional[UUID] = None
    date: date
    hours_slept: Optional[float] = None
    sleep_quality: Optional[int] = None
    bedtime: Optional[time] = None
    wake_time: Optional[time] = None
    wakeups: Optional[int] = None
    tiredness_on_wake: Optional[int] = None
    tiredness_during_day: Optional[int] = None
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SleepLogSummaryResponse(BaseModel):
    period_start: date
    period_end: date
    total_logs: int
    days_with_log: int
    days_without_log: int
    avg_hours_slept: Optional[float] = None
    avg_sleep_quality: Optional[float] = None
    avg_wakeups: Optional[float] = None
    avg_tiredness_on_wake: Optional[float] = None
    avg_tiredness_during_day: Optional[float] = None
    hours_trend: str
    quality_trend: str
