from datetime import date as date_type, datetime, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.health import ConditionCategory, ConditionStatus, EpisodeType, GuidelineKind


class HealthGuidelineCreate(BaseModel):
    kind: GuidelineKind
    text: str = Field(min_length=1, max_length=4000)
    is_done: bool = False
    sort_order: int = Field(default=0, ge=0)


class HealthGuidelineUpdate(BaseModel):
    kind: Optional[GuidelineKind] = None
    text: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    is_done: Optional[bool] = None
    sort_order: Optional[int] = Field(default=None, ge=0)


class HealthGuidelineResponse(BaseModel):
    id: UUID
    condition_id: UUID
    kind: GuidelineKind
    text: str
    is_done: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HealthReminderCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    time_of_day: Optional[time] = None
    frequency: str = Field(default="daily", min_length=1, max_length=80)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0)


class HealthReminderUpdate(BaseModel):
    text: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    time_of_day: Optional[time] = None
    frequency: Optional[str] = Field(default=None, min_length=1, max_length=80)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = Field(default=None, ge=0)


class HealthReminderResponse(BaseModel):
    id: UUID
    condition_id: UUID
    text: str
    time_of_day: Optional[time] = None
    frequency: str
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HealthConditionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category: ConditionCategory = ConditionCategory.other
    status: ConditionStatus = ConditionStatus.active
    description: Optional[str] = Field(default=None, max_length=4000)
    diagnosed_on: Optional[date_type] = None
    notes: Optional[str] = Field(default=None, max_length=4000)


class HealthConditionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    category: Optional[ConditionCategory] = None
    status: Optional[ConditionStatus] = None
    description: Optional[str] = Field(default=None, max_length=4000)
    diagnosed_on: Optional[date_type] = None
    notes: Optional[str] = Field(default=None, max_length=4000)


class HealthConditionResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    category: ConditionCategory
    status: ConditionStatus
    description: Optional[str] = None
    diagnosed_on: Optional[date_type] = None
    notes: Optional[str] = None
    guidelines: list[HealthGuidelineResponse] = Field(default_factory=list)
    reminders: list[HealthReminderResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SicknessEpisodeCreate(BaseModel):
    condition_id: Optional[UUID] = None
    episode_type: EpisodeType
    title: str = Field(min_length=1, max_length=160)
    started_on: date_type
    ended_on: Optional[date_type] = None
    severity: Optional[int] = Field(default=None, ge=1, le=5)
    symptoms: Optional[str] = Field(default=None, max_length=4000)
    notes: Optional[str] = Field(default=None, max_length=4000)


class SicknessEpisodeUpdate(BaseModel):
    condition_id: Optional[UUID] = None
    episode_type: Optional[EpisodeType] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=160)
    started_on: Optional[date_type] = None
    ended_on: Optional[date_type] = None
    severity: Optional[int] = Field(default=None, ge=1, le=5)
    symptoms: Optional[str] = Field(default=None, max_length=4000)
    notes: Optional[str] = Field(default=None, max_length=4000)


class SicknessEpisodeResponse(BaseModel):
    id: UUID
    user_id: UUID
    condition_id: Optional[UUID] = None
    episode_type: EpisodeType
    title: str
    started_on: date_type
    ended_on: Optional[date_type] = None
    severity: Optional[int] = None
    symptoms: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SicknessEpisodeSummaryResponse(BaseModel):
    period_start: date_type
    period_end: date_type
    total: int
    by_type: dict[str, int]


class GuidelineSuggestionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category: Optional[ConditionCategory] = None


class GuidelineSuggestionResponse(BaseModel):
    avoid: list[str]
    helps: list[str]
    action_plan: list[str]
