import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.project import Base


class HabitCategory(str, enum.Enum):
    substance = "substance"
    behavior = "behavior"
    digital = "digital"
    other = "other"


class HabitTrackingMode(str, enum.Enum):
    positive = "positive"
    abstinence = "abstinence"
    control = "control"


class HabitStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    achieved = "achieved"
    abandoned = "abandoned"


class HabitEventType(str, enum.Enum):
    check_in = "check_in"
    urge = "urge"
    relapse = "relapse"


class Habit(Base):
    __tablename__ = "habits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(160), nullable=False)
    category = Column(SAEnum(HabitCategory), nullable=False, default=HabitCategory.other)
    tracking_mode = Column(SAEnum(HabitTrackingMode), nullable=False, default=HabitTrackingMode.positive)
    status = Column(SAEnum(HabitStatus), nullable=False, default=HabitStatus.active)
    motivation = Column(Text, nullable=True)
    triggers = Column(JSON, nullable=False, default=list)
    coping_strategies = Column(JSON, nullable=False, default=list)
    action_plan = Column(Text, nullable=True)
    start_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="habits")
    events = relationship("HabitEvent", back_populates="habit", cascade="all, delete-orphan", order_by="HabitEvent.occurred_at.desc()")


class HabitEvent(Base):
    __tablename__ = "habit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    habit_id = Column(UUID(as_uuid=True), ForeignKey("habits.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(SAEnum(HabitEventType), nullable=False)
    occurred_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    intensity = Column(Integer, nullable=True)
    emotion = Column(String(80), nullable=True)
    trigger = Column(String(120), nullable=True)
    feeling_note = Column(Text, nullable=True)
    thought = Column(Text, nullable=True)
    action_taken = Column(Text, nullable=True)
    resisted = Column(Boolean, nullable=True)
    breathing_used = Column(Boolean, default=False, nullable=False)
    emotion_entry_id = Column(UUID(as_uuid=True), ForeignKey("emotion_entries.id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="habit_events")
    habit = relationship("Habit", back_populates="events")
    emotion_entry = relationship("EmotionEntry", foreign_keys=[emotion_entry_id])
