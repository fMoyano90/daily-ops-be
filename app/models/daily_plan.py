import uuid
from datetime import datetime, date

from sqlalchemy import Column, String, Text, DateTime, Date, Enum as SAEnum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.models.project import Base


class DailyPlanStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class DailyPlan(Base):
    __tablename__ = "daily_plans"
    __table_args__ = (UniqueConstraint("date", name="uq_daily_plans_date"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(Date, nullable=False, unique=True)
    status = Column(SAEnum(DailyPlanStatus), nullable=False, default=DailyPlanStatus.open)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    tasks = relationship("DailyTask", back_populates="daily_plan", cascade="all, delete-orphan", order_by="DailyTask.sort_order")
