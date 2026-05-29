import uuid
from datetime import datetime, date, timezone

from sqlalchemy import Column, String, Text, DateTime, Date, Enum as SAEnum, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.models.project import Base


class DailyPlanStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class DailyPlan(Base):
    __tablename__ = "daily_plans"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_daily_plans_user_date"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    status = Column(SAEnum(DailyPlanStatus), nullable=False, default=DailyPlanStatus.open)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="daily_plans")
    tasks = relationship("DailyTask", back_populates="daily_plan", cascade="all, delete-orphan", order_by="DailyTask.sort_order")
    emotion_entries = relationship("EmotionEntry", back_populates="daily_plan")
