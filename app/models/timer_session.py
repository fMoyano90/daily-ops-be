import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.project import Base


class TimerSession(Base):
    __tablename__ = "timer_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    daily_task_id = Column(UUID(as_uuid=True), ForeignKey("daily_tasks.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    stopped_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=False, default=0)

    daily_task = relationship("DailyTask", back_populates="timer_sessions")
