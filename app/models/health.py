import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.project import Base


class ConditionCategory(str, enum.Enum):
    cardiovascular = "cardiovascular"
    metabolic = "metabolic"
    dental = "dental"
    mental = "mental"
    respiratory = "respiratory"
    other = "other"


class ConditionStatus(str, enum.Enum):
    active = "active"
    monitoring = "monitoring"
    resolved = "resolved"


class GuidelineKind(str, enum.Enum):
    avoid = "avoid"
    helps = "helps"
    action = "action"


class EpisodeType(str, enum.Enum):
    cold = "cold"
    flu = "flu"
    physical = "physical"
    mental = "mental"
    other = "other"


class HealthCondition(Base):
    __tablename__ = "health_conditions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(160), nullable=False)
    category = Column(SAEnum(ConditionCategory), nullable=False)
    status = Column(SAEnum(ConditionStatus), nullable=False, default=ConditionStatus.active)
    description = Column(Text, nullable=True)
    diagnosed_on = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="health_conditions")
    guidelines = relationship(
        "HealthGuideline",
        back_populates="condition",
        cascade="all, delete-orphan",
        order_by="HealthGuideline.sort_order",
    )
    reminders = relationship(
        "HealthReminder",
        back_populates="condition",
        cascade="all, delete-orphan",
        order_by="HealthReminder.sort_order",
    )
    episodes = relationship("SicknessEpisode", back_populates="condition")


class HealthGuideline(Base):
    __tablename__ = "health_guidelines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    condition_id = Column(UUID(as_uuid=True), ForeignKey("health_conditions.id", ondelete="CASCADE"), nullable=False)
    kind = Column(SAEnum(GuidelineKind), nullable=False)
    text = Column(Text, nullable=False)
    is_done = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    condition = relationship("HealthCondition", back_populates="guidelines")


class HealthReminder(Base):
    __tablename__ = "health_reminders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    condition_id = Column(UUID(as_uuid=True), ForeignKey("health_conditions.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    time_of_day = Column(Time, nullable=True)
    frequency = Column(String(80), nullable=False, default="daily")
    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    condition = relationship("HealthCondition", back_populates="reminders")


class SicknessEpisode(Base):
    __tablename__ = "sickness_episodes"
    __table_args__ = (
        CheckConstraint("severity IS NULL OR (severity >= 1 AND severity <= 5)", name="ck_sickness_episodes_severity"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    condition_id = Column(UUID(as_uuid=True), ForeignKey("health_conditions.id", ondelete="SET NULL"), nullable=True)
    episode_type = Column(SAEnum(EpisodeType), nullable=False)
    title = Column(String(160), nullable=False)
    started_on = Column(Date, nullable=False)
    ended_on = Column(Date, nullable=True)
    severity = Column(Integer, nullable=True)
    symptoms = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="sickness_episodes")
    condition = relationship("HealthCondition", back_populates="episodes")
