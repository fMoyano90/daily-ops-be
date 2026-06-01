import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Enum as SAEnum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.project import Base


class Sex(str, enum.Enum):
    male = "male"
    female = "female"


class ActivityLevel(str, enum.Enum):
    sedentary = "sedentary"
    light = "light"
    moderate = "moderate"
    active = "active"
    very_active = "very_active"


class NutritionGoal(str, enum.Enum):
    lose = "lose"
    maintain = "maintain"
    gain = "gain"


class NutritionDayStatus(str, enum.Enum):
    draft = "draft"
    analyzed = "analyzed"


class HealthProfile(Base):
    __tablename__ = "health_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_health_profiles_user_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sex = Column(SAEnum(Sex), nullable=False)
    birth_date = Column(Date, nullable=False)
    height_cm = Column(Float, nullable=False)
    weight_kg = Column(Float, nullable=False)
    activity_level = Column(SAEnum(ActivityLevel), nullable=False)
    goal = Column(SAEnum(NutritionGoal), nullable=False)
    target_calories_override = Column(Integer, nullable=True)
    glass_ml = Column(Integer, nullable=False, default=200)
    country = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="health_profile")


class NutritionDay(Base):
    __tablename__ = "nutrition_days"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_nutrition_days_user_date"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    daily_plan_id = Column(UUID(as_uuid=True), ForeignKey("daily_plans.id", ondelete="SET NULL"), nullable=True)
    date = Column(Date, nullable=False)
    water_ml = Column(Integer, nullable=False, default=0)
    day_note = Column(Text, nullable=True)
    status = Column(SAEnum(NutritionDayStatus), nullable=False, default=NutritionDayStatus.draft)
    analyzed_at = Column(DateTime(timezone=True), nullable=True)
    ai_model = Column(String(120), nullable=True)
    ai_summary = Column(Text, nullable=True)
    recommended_calories = Column(Integer, nullable=True)
    consumed_calories = Column(Integer, nullable=True)
    burned_calories = Column(Integer, nullable=True)
    balance_calories = Column(Integer, nullable=True)
    total_protein_g = Column(Float, nullable=True)
    total_carbs_g = Column(Float, nullable=True)
    total_sugar_g = Column(Float, nullable=True)
    total_fat_g = Column(Float, nullable=True)
    total_fiber_g = Column(Float, nullable=True)
    ai_meal_plan = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="nutrition_days")
    daily_plan = relationship("DailyPlan", back_populates="nutrition_days")


class MealEntry(Base):
    __tablename__ = "meal_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    daily_plan_id = Column(UUID(as_uuid=True), ForeignKey("daily_plans.id", ondelete="SET NULL"), nullable=True)
    date = Column(Date, nullable=False)
    label = Column(String(80), nullable=False)
    description = Column(Text, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    calories = Column(Integer, nullable=True)
    protein_g = Column(Float, nullable=True)
    carbs_g = Column(Float, nullable=True)
    sugar_g = Column(Float, nullable=True)
    fat_g = Column(Float, nullable=True)
    fiber_g = Column(Float, nullable=True)
    ai_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="meal_entries")
    daily_plan = relationship("DailyPlan", back_populates="meal_entries")


class ExerciseEntry(Base):
    __tablename__ = "exercise_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    daily_plan_id = Column(UUID(as_uuid=True), ForeignKey("daily_plans.id", ondelete="SET NULL"), nullable=True)
    date = Column(Date, nullable=False)
    label = Column(String(80), nullable=False)
    description = Column(Text, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    calories_burned = Column(Integer, nullable=True)
    duration_min = Column(Integer, nullable=True)
    intensity = Column(String(80), nullable=True)
    ai_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="exercise_entries")
    daily_plan = relationship("DailyPlan", back_populates="exercise_entries")


class WeightEntry(Base):
    __tablename__ = "weight_entries"
    __table_args__ = (UniqueConstraint("user_id", "recorded_at", name="uq_weight_entries_user_date"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    weight_kg = Column(Float, nullable=False)
    recorded_at = Column(Date, nullable=False)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User")


class PantryItem(Base):
    __tablename__ = "pantry_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    is_available = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User")
