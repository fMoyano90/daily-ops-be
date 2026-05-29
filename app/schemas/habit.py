from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.habit import HabitCategory, HabitEventType, HabitStatus, HabitTrackingMode


class HabitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category: HabitCategory = HabitCategory.other
    tracking_mode: HabitTrackingMode = HabitTrackingMode.abstinence
    motivation: Optional[str] = None
    triggers: list[str] = Field(default_factory=list)
    coping_strategies: list[str] = Field(default_factory=list)
    action_plan: Optional[str] = None
    start_date: Optional[datetime] = None

    @field_validator("triggers", "coping_strategies")
    @classmethod
    def limit_list(cls, value: list[str]) -> list[str]:
        return [item.strip()[:120] for item in value if item.strip()][:20]


class HabitUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    category: Optional[HabitCategory] = None
    tracking_mode: Optional[HabitTrackingMode] = None
    status: Optional[HabitStatus] = None
    motivation: Optional[str] = None
    triggers: Optional[list[str]] = None
    coping_strategies: Optional[list[str]] = None
    action_plan: Optional[str] = None
    start_date: Optional[datetime] = None

    @field_validator("triggers", "coping_strategies")
    @classmethod
    def limit_list(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return value
        return [item.strip()[:120] for item in value if item.strip()][:20]


class HabitResponse(BaseModel):
    id: UUID
    name: str
    category: HabitCategory
    tracking_mode: HabitTrackingMode
    status: HabitStatus
    motivation: Optional[str] = None
    triggers: list[str] = Field(default_factory=list)
    coping_strategies: list[str] = Field(default_factory=list)
    action_plan: Optional[str] = None
    start_date: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HabitEventCreate(BaseModel):
    event_type: HabitEventType
    occurred_at: Optional[datetime] = None
    intensity: Optional[int] = Field(default=None, ge=1, le=10)
    emotion: Optional[str] = Field(default=None, max_length=80)
    trigger: Optional[str] = Field(default=None, max_length=120)
    feeling_note: Optional[str] = None
    thought: Optional[str] = None
    action_taken: Optional[str] = None
    resisted: Optional[bool] = None
    breathing_used: bool = False
    note: Optional[str] = None
    mirror_to_emotions: bool = False


class HabitEventUpdate(BaseModel):
    event_type: Optional[HabitEventType] = None
    occurred_at: Optional[datetime] = None
    intensity: Optional[int] = Field(default=None, ge=1, le=10)
    emotion: Optional[str] = Field(default=None, max_length=80)
    trigger: Optional[str] = Field(default=None, max_length=120)
    feeling_note: Optional[str] = None
    thought: Optional[str] = None
    action_taken: Optional[str] = None
    resisted: Optional[bool] = None
    breathing_used: Optional[bool] = None
    note: Optional[str] = None


class HabitEventResponse(BaseModel):
    id: UUID
    habit_id: UUID
    event_type: HabitEventType
    occurred_at: datetime
    intensity: Optional[int] = None
    emotion: Optional[str] = None
    trigger: Optional[str] = None
    feeling_note: Optional[str] = None
    thought: Optional[str] = None
    action_taken: Optional[str] = None
    resisted: Optional[bool] = None
    breathing_used: bool
    emotion_entry_id: Optional[UUID] = None
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HabitMetrics(BaseModel):
    current_streak_days: int
    longest_streak_days: int
    days_since_last_relapse: Optional[int]
    total_relapses: int
    total_urges: int
    urges_resisted: int
    urge_resistance_rate: float


class HabitSummaryResponse(BaseModel):
    start_date: date
    end_date: date
    total_events: int
    relapses: int
    urges: int
    check_ins: int
    urges_resisted: int
    urge_resistance_rate: float
    dominant_trigger: Optional[str] = None
    dominant_emotion: Optional[str] = None
    avg_intensity: float
    metrics: HabitMetrics
