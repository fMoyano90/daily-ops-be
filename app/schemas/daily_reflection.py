from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DailyReflectionCreate(BaseModel):
    went_well: Optional[str] = None
    drained_me: Optional[str] = None
    learned: Optional[str] = None
    grateful_for: Optional[str] = None
    improve_tomorrow: Optional[str] = None
    mood_rating: Optional[int] = Field(default=None, ge=1, le=10)
    energy_rating: Optional[int] = Field(default=None, ge=1, le=10)
    productivity_rating: Optional[int] = Field(default=None, ge=1, le=10)
    note: Optional[str] = None


class DailyReflectionUpdate(BaseModel):
    went_well: Optional[str] = None
    drained_me: Optional[str] = None
    learned: Optional[str] = None
    grateful_for: Optional[str] = None
    improve_tomorrow: Optional[str] = None
    mood_rating: Optional[int] = Field(default=None, ge=1, le=10)
    energy_rating: Optional[int] = Field(default=None, ge=1, le=10)
    productivity_rating: Optional[int] = Field(default=None, ge=1, le=10)
    note: Optional[str] = None


class DailyReflectionResponse(BaseModel):
    id: UUID
    user_id: UUID
    daily_plan_id: Optional[UUID] = None
    went_well: Optional[str] = None
    drained_me: Optional[str] = None
    learned: Optional[str] = None
    grateful_for: Optional[str] = None
    improve_tomorrow: Optional[str] = None
    mood_rating: Optional[int] = None
    energy_rating: Optional[int] = None
    productivity_rating: Optional[int] = None
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DailyReflectionSummaryResponse(BaseModel):
    period_start: date
    period_end: date
    total_reflections: int
    days_with_reflection: int
    days_without_reflection: int
    avg_mood: Optional[float] = None
    avg_energy: Optional[float] = None
    avg_productivity: Optional[float] = None
    mood_trend: str
    energy_trend: str
    productivity_trend: str
