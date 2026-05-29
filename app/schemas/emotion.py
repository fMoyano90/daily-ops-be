from datetime import datetime, date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.emotion import EmotionEnergy, EmotionValence, TaskEmotionPhase


class EmotionEntryCreate(BaseModel):
    daily_plan_id: Optional[UUID] = None
    daily_task_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    task_phase: Optional[TaskEmotionPhase] = None
    emotion: str = Field(min_length=1, max_length=80)
    secondary_emotions: list[str] = Field(default_factory=list)
    intensity: int = Field(ge=1, le=10)
    valence: EmotionValence
    energy: EmotionEnergy = EmotionEnergy.medium
    trigger_type: Optional[str] = Field(default=None, max_length=80)
    trigger_note: Optional[str] = None
    body_sensation: Optional[str] = None
    thought: Optional[str] = None
    need: Optional[str] = None
    response: Optional[str] = None
    regulation_strategy: Optional[str] = Field(default=None, max_length=120)
    strategy_helped: Optional[str] = Field(default=None, max_length=20)
    note: Optional[str] = None
    occurred_at: Optional[datetime] = None

    @field_validator("secondary_emotions")
    @classmethod
    def limit_secondary_emotions(cls, value: list[str]) -> list[str]:
        return [item.strip()[:80] for item in value if item.strip()][:8]

    @model_validator(mode="after")
    def validate_task_phase(self):
        if self.task_phase and not self.daily_task_id:
            raise ValueError("task_phase requires daily_task_id")
        return self


class EmotionEntryUpdate(BaseModel):
    daily_plan_id: Optional[UUID] = None
    daily_task_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    task_phase: Optional[TaskEmotionPhase] = None
    emotion: Optional[str] = Field(default=None, min_length=1, max_length=80)
    secondary_emotions: Optional[list[str]] = None
    intensity: Optional[int] = Field(default=None, ge=1, le=10)
    valence: Optional[EmotionValence] = None
    energy: Optional[EmotionEnergy] = None
    trigger_type: Optional[str] = Field(default=None, max_length=80)
    trigger_note: Optional[str] = None
    body_sensation: Optional[str] = None
    thought: Optional[str] = None
    need: Optional[str] = None
    response: Optional[str] = None
    regulation_strategy: Optional[str] = Field(default=None, max_length=120)
    strategy_helped: Optional[str] = Field(default=None, max_length=20)
    note: Optional[str] = None
    occurred_at: Optional[datetime] = None

    @field_validator("secondary_emotions")
    @classmethod
    def limit_secondary_emotions(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return value
        return [item.strip()[:80] for item in value if item.strip()][:8]

    @model_validator(mode="after")
    def validate_task_phase(self):
        if self.task_phase and not self.daily_task_id:
            raise ValueError("task_phase requires daily_task_id")
        return self


class EmotionEntryResponse(BaseModel):
    id: UUID
    daily_plan_id: Optional[UUID] = None
    daily_task_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    task_phase: Optional[TaskEmotionPhase] = None
    emotion: str
    secondary_emotions: list[str] = Field(default_factory=list)
    intensity: int
    valence: EmotionValence
    energy: EmotionEnergy
    trigger_type: Optional[str] = None
    trigger_note: Optional[str] = None
    body_sensation: Optional[str] = None
    thought: Optional[str] = None
    need: Optional[str] = None
    response: Optional[str] = None
    regulation_strategy: Optional[str] = None
    strategy_helped: Optional[str] = None
    note: Optional[str] = None
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EmotionSummaryResponse(BaseModel):
    start_date: date
    end_date: date
    total_entries: int
    average_intensity: float
    dominant_emotion: Optional[str] = None
    dominant_trigger: Optional[str] = None
    unpleasant_count: int
    pleasant_count: int
    neutral_count: int
    by_emotion: dict[str, int]
    by_trigger: dict[str, int]
    by_valence: dict[str, int]
