from datetime import date as date_type, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.nutrition import ActivityLevel, NutritionGoal, NutritionDayStatus, Sex


class HealthProfileUpsert(BaseModel):
    sex: Sex
    birth_date: date_type
    height_cm: float = Field(gt=0, le=260)
    weight_kg: float = Field(gt=0, le=500)
    activity_level: ActivityLevel
    goal: NutritionGoal
    target_calories_override: Optional[int] = Field(default=None, ge=800, le=10000)
    glass_ml: int = Field(default=200, ge=50, le=1000)


class HealthProfileResponse(HealthProfileUpsert):
    id: UUID
    user_id: UUID
    age: int
    bmr: int
    tdee: int
    recommended_calories: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MealEntryCreate(BaseModel):
    date: Optional[date_type] = None
    label: Optional[str] = Field(default=None, max_length=80)
    description: str = Field(min_length=1, max_length=4000)


class MealEntryUpdate(BaseModel):
    label: Optional[str] = Field(default=None, max_length=80)
    description: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    sort_order: Optional[int] = Field(default=None, ge=0)


class MealEntryResponse(BaseModel):
    id: UUID
    user_id: UUID
    daily_plan_id: Optional[UUID] = None
    date: date_type
    label: str
    description: str
    sort_order: int
    calories: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    sugar_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    ai_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExerciseEntryCreate(BaseModel):
    date: Optional[date_type] = None
    label: Optional[str] = Field(default=None, max_length=80)
    description: str = Field(min_length=1, max_length=4000)


class ExerciseEntryUpdate(BaseModel):
    label: Optional[str] = Field(default=None, max_length=80)
    description: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    sort_order: Optional[int] = Field(default=None, ge=0)


class ExerciseEntryResponse(BaseModel):
    id: UUID
    user_id: UUID
    daily_plan_id: Optional[UUID] = None
    date: date_type
    label: str
    description: str
    sort_order: int
    calories_burned: Optional[int] = None
    duration_min: Optional[int] = None
    intensity: Optional[str] = None
    ai_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WaterUpdate(BaseModel):
    delta: Optional[int] = Field(default=None, ge=-100, le=100)
    water_ml: Optional[int] = Field(default=None, ge=0, le=20000)

    @model_validator(mode="after")
    def require_delta_or_value(self):
        if self.delta is None and self.water_ml is None:
            raise ValueError("delta or water_ml is required")
        return self


class NutritionDayResponse(BaseModel):
    id: UUID
    user_id: UUID
    daily_plan_id: Optional[UUID] = None
    date: date_type
    water_ml: int
    day_note: Optional[str] = None
    status: NutritionDayStatus
    analyzed_at: Optional[datetime] = None
    ai_model: Optional[str] = None
    ai_summary: Optional[str] = None
    recommended_calories: Optional[int] = None
    consumed_calories: Optional[int] = None
    burned_calories: Optional[int] = None
    balance_calories: Optional[int] = None
    total_protein_g: Optional[float] = None
    total_carbs_g: Optional[float] = None
    total_sugar_g: Optional[float] = None
    total_fat_g: Optional[float] = None
    total_fiber_g: Optional[float] = None
    meals: list[MealEntryResponse] = Field(default_factory=list)
    exercises: list[ExerciseEntryResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NutritionDaySummaryResponse(BaseModel):
    period_start: date_type
    period_end: date_type
    total_days: int
    analyzed_days: int
    avg_recommended_calories: Optional[float] = None
    avg_consumed_calories: Optional[float] = None
    avg_burned_calories: Optional[float] = None
    avg_balance_calories: Optional[float] = None
    total_water_ml: int
    avg_protein_g: Optional[float] = None
    avg_carbs_g: Optional[float] = None
    avg_sugar_g: Optional[float] = None
    avg_fat_g: Optional[float] = None
