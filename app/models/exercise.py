import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Enum as SAEnum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from sqlalchemy.orm import relationship

from app.models.project import Base


class ExerciseDayStatus(str, enum.Enum):
    draft = "draft"
    completed = "completed"


class ExerciseType(str, enum.Enum):
    strength = "strength"
    cardio = "cardio"
    mobility = "mobility"
    recovery = "recovery"


class WorkoutExerciseStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    partial = "partial"
    skipped = "skipped"


class ExerciseProfile(Base):
    __tablename__ = "exercise_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_exercise_profiles_user_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    available_days = Column(JSONB, nullable=False, default=list)  # [0..6] — 0=Mon..6=Sun
    location = Column(String(80), nullable=True)  # 'home' | 'gym' | 'outdoor' | 'mixed'
    equipment = Column(JSONB, nullable=False, default=list)
    session_duration_min = Column(Integer, nullable=True)
    fitness_level = Column(String(40), nullable=True)  # 'beginner' | 'intermediate' | 'advanced'
    physical_restrictions = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="exercise_profile")


class WorkoutDay(Base):
    __tablename__ = "workout_days"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_workout_days_user_date"),
        Index("ix_workout_days_user_date", "user_id", "date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    daily_plan_id = Column(UUID(as_uuid=True), ForeignKey("daily_plans.id", ondelete="SET NULL"), nullable=True)
    date = Column(Date, nullable=False)
    status = Column(SAEnum(ExerciseDayStatus), nullable=False, default=ExerciseDayStatus.draft)
    total_calories_burned = Column(Integer, nullable=True)
    total_duration_min = Column(Integer, nullable=True)
    rpe = Column(Integer, nullable=True)  # 1-10 perceived exertion
    post_workout_state = Column(String(80), nullable=True)
    day_note = Column(Text, nullable=True)
    coach_notes = Column(Text, nullable=True)
    ai_model = Column(String(120), nullable=True)
    analyzed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="workout_days")


class WorkoutExercise(Base):
    __tablename__ = "workout_exercises"
    __table_args__ = (
        Index("ix_workout_exercises_user_date", "user_id", "date"),
        Index("ix_workout_exercises_workout_day_id", "workout_day_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workout_day_id = Column(UUID(as_uuid=True), ForeignKey("workout_days.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    name = Column(String(120), nullable=False)
    exercise_type = Column(SAEnum(ExerciseType), nullable=False, default=ExerciseType.cardio)
    muscle_group = Column(String(80), nullable=True)
    sets = Column(Integer, nullable=True)
    reps = Column(Integer, nullable=True)
    weight_kg = Column(Float, nullable=True)
    duration_min = Column(Integer, nullable=True)
    distance_km = Column(Float, nullable=True)
    calories_burned = Column(Integer, nullable=True)
    intensity = Column(String(40), nullable=True)  # 'low' | 'moderate' | 'high'
    sort_order = Column(Integer, nullable=False, default=0)
    status = Column(SAEnum(WorkoutExerciseStatus), nullable=False, default=WorkoutExerciseStatus.pending)
    ai_suggested = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    ai_notes = Column(Text, nullable=True)
    rest_seconds_recommended = Column(Integer, nullable=True)
    sets_data = Column(JSONB, nullable=True)
    timer_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="workout_exercises")
