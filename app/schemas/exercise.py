from datetime import date as date_type, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.exercise import ExerciseDayStatus, ExerciseType, WorkoutExerciseStatus


class ExerciseProfileUpsert(BaseModel):
    available_days: list[int] = Field(default_factory=list)  # [0..6]
    location: Optional[str] = Field(default=None, max_length=80)
    equipment: list[str] = Field(default_factory=list)
    session_duration_min: Optional[int] = Field(default=None, ge=5, le=300)
    fitness_level: Optional[str] = Field(default=None, max_length=40)
    physical_restrictions: Optional[str] = Field(default=None, max_length=2000)


class ExerciseProfileResponse(ExerciseProfileUpsert):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkoutExerciseCreate(BaseModel):
    date: Optional[date_type] = None
    name: str = Field(min_length=1, max_length=120)
    exercise_type: ExerciseType = ExerciseType.cardio
    muscle_group: Optional[str] = Field(default=None, max_length=80)
    sets: Optional[int] = Field(default=None, ge=1, le=100)
    reps: Optional[int] = Field(default=None, ge=1, le=1000)
    weight_kg: Optional[float] = Field(default=None, ge=0, le=1000)
    duration_min: Optional[int] = Field(default=None, ge=1, le=600)
    distance_km: Optional[float] = Field(default=None, ge=0, le=1000)
    calories_burned: Optional[int] = Field(default=None, ge=0, le=10000)
    intensity: Optional[str] = Field(default=None, max_length=40)
    notes: Optional[str] = Field(default=None, max_length=2000)
    rest_seconds_recommended: Optional[int] = Field(default=None, ge=10, le=600)


class WorkoutExerciseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    exercise_type: Optional[ExerciseType] = None
    muscle_group: Optional[str] = Field(default=None, max_length=80)
    sets: Optional[int] = Field(default=None, ge=1, le=100)
    reps: Optional[int] = Field(default=None, ge=1, le=1000)
    weight_kg: Optional[float] = Field(default=None, ge=0, le=1000)
    duration_min: Optional[int] = Field(default=None, ge=1, le=600)
    distance_km: Optional[float] = Field(default=None, ge=0, le=1000)
    calories_burned: Optional[int] = Field(default=None, ge=0, le=10000)
    intensity: Optional[str] = Field(default=None, max_length=40)
    status: Optional[WorkoutExerciseStatus] = None
    sort_order: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=2000)
    rest_seconds_recommended: Optional[int] = Field(default=None, ge=10, le=600)
    sets_data: Optional[list[dict]] = None
    timer_seconds: Optional[int] = Field(default=None, ge=0)


class WorkoutExerciseResponse(BaseModel):
    id: UUID
    user_id: UUID
    workout_day_id: UUID
    date: date_type
    name: str
    exercise_type: ExerciseType
    muscle_group: Optional[str] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    duration_min: Optional[int] = None
    distance_km: Optional[float] = None
    calories_burned: Optional[int] = None
    intensity: Optional[str] = None
    sort_order: int
    status: WorkoutExerciseStatus
    ai_suggested: bool
    notes: Optional[str] = None
    ai_notes: Optional[str] = None
    rest_seconds_recommended: Optional[int] = None
    sets_data: Optional[list[dict]] = None
    timer_seconds: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkoutDayUpdate(BaseModel):
    rpe: Optional[int] = Field(default=None, ge=1, le=10)
    post_workout_state: Optional[str] = Field(default=None, max_length=80)
    day_note: Optional[str] = Field(default=None, max_length=4000)
    status: Optional[ExerciseDayStatus] = None


class WorkoutDayResponse(BaseModel):
    id: UUID
    user_id: UUID
    daily_plan_id: Optional[UUID] = None
    date: date_type
    status: ExerciseDayStatus
    total_calories_burned: Optional[int] = None
    total_duration_min: Optional[int] = None
    rpe: Optional[int] = None
    post_workout_state: Optional[str] = None
    day_note: Optional[str] = None
    coach_notes: Optional[str] = None
    ai_model: Optional[str] = None
    analyzed_at: Optional[datetime] = None
    exercises: list[WorkoutExerciseResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkoutWeekSummaryResponse(BaseModel):
    period_start: date_type
    period_end: date_type
    total_days: int
    trained_days: int
    rest_days: int
    total_calories_burned: int
    total_duration_min: int
    avg_rpe: Optional[float] = None
    streak_days: int


class DailyContextInput(BaseModel):
    energy_level: Optional[str] = Field(default=None, max_length=40)  # 'high' | 'normal' | 'low' | 'exhausted'
    available_time_min: Optional[int] = Field(default=None, ge=5, le=300)
    focus_area: Optional[str] = Field(default=None, max_length=80)  # 'upper' | 'lower' | 'core' | 'full' | 'cardio'
    notes: Optional[str] = Field(default=None, max_length=1000)
