import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.models.project import Base
from app.models.task import Priority


class DailyTaskStatus(str, enum.Enum):
    planned = "planned"
    in_progress = "in_progress"
    paused = "paused"
    completed = "completed"
    rolled_over = "rolled_over"
    skipped = "skipped"


class DailyTask(Base):
    __tablename__ = "daily_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    daily_plan_id = Column(UUID(as_uuid=True), ForeignKey("daily_plans.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    recurring_task_id = Column(UUID(as_uuid=True), ForeignKey("recurring_tasks.id", ondelete="SET NULL"), nullable=True)
    title_snapshot = Column(String(500), nullable=False)
    priority = Column(SAEnum(Priority, name="priority"), nullable=False)
    status = Column(SAEnum(DailyTaskStatus, name="dailytaskstatus"), nullable=False, default=DailyTaskStatus.planned)
    total_seconds = Column(Integer, nullable=False, default=0)
    sort_order = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="daily_tasks")
    daily_plan = relationship("DailyPlan", back_populates="tasks")
    task = relationship("Task", back_populates="daily_tasks")
    recurring_task = relationship("RecurringTask")
    subtasks = relationship("DailySubtask", back_populates="daily_task", cascade="all, delete-orphan", order_by="DailySubtask.sort_order")
    timer_sessions = relationship("TimerSession", back_populates="daily_task", cascade="all, delete-orphan")
    emotion_entries = relationship("EmotionEntry", back_populates="daily_task")
