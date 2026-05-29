import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.project import Base


class EmotionValence(str, enum.Enum):
    pleasant = "pleasant"
    neutral = "neutral"
    unpleasant = "unpleasant"


class EmotionEnergy(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TaskEmotionPhase(str, enum.Enum):
    before = "before"
    after = "after"


class EmotionEntry(Base):
    __tablename__ = "emotion_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    daily_plan_id = Column(UUID(as_uuid=True), ForeignKey("daily_plans.id", ondelete="SET NULL"), nullable=True)
    daily_task_id = Column(UUID(as_uuid=True), ForeignKey("daily_tasks.id", ondelete="SET NULL"), nullable=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    task_phase = Column(SAEnum(TaskEmotionPhase), nullable=True)
    emotion = Column(String(80), nullable=False)
    secondary_emotions = Column(JSON, nullable=False, default=list)
    intensity = Column(Integer, nullable=False)
    valence = Column(SAEnum(EmotionValence), nullable=False)
    energy = Column(SAEnum(EmotionEnergy), nullable=False, default=EmotionEnergy.medium)
    trigger_type = Column(String(80), nullable=True)
    trigger_note = Column(Text, nullable=True)
    body_sensation = Column(Text, nullable=True)
    thought = Column(Text, nullable=True)
    need = Column(Text, nullable=True)
    response = Column(Text, nullable=True)
    regulation_strategy = Column(String(120), nullable=True)
    strategy_helped = Column(String(20), nullable=True)
    note = Column(Text, nullable=True)
    occurred_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="emotion_entries")
    daily_plan = relationship("DailyPlan", back_populates="emotion_entries")
    daily_task = relationship("DailyTask", back_populates="emotion_entries")
    project = relationship("Project", back_populates="emotion_entries")
