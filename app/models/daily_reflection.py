import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.project import Base


class DailyReflection(Base):
    __tablename__ = "daily_reflections"
    __table_args__ = (
        CheckConstraint("mood_rating IS NULL OR (mood_rating >= 1 AND mood_rating <= 10)", name="ck_daily_reflections_mood_rating"),
        CheckConstraint("energy_rating IS NULL OR (energy_rating >= 1 AND energy_rating <= 10)", name="ck_daily_reflections_energy_rating"),
        CheckConstraint("productivity_rating IS NULL OR (productivity_rating >= 1 AND productivity_rating <= 10)", name="ck_daily_reflections_productivity_rating"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    daily_plan_id = Column(UUID(as_uuid=True), ForeignKey("daily_plans.id", ondelete="SET NULL"), nullable=True, unique=True)
    went_well = Column(Text, nullable=True)
    drained_me = Column(Text, nullable=True)
    learned = Column(Text, nullable=True)
    grateful_for = Column(Text, nullable=True)
    improve_tomorrow = Column(Text, nullable=True)
    mood_rating = Column(Integer, nullable=True)
    energy_rating = Column(Integer, nullable=True)
    productivity_rating = Column(Integer, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="daily_reflections")
    daily_plan = relationship("DailyPlan", back_populates="daily_reflection")
