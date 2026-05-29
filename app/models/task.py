import uuid
from datetime import datetime, date, timezone

from sqlalchemy import Column, String, Text, DateTime, Date, Time, Integer, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.models.project import Base


class TaskSource(str, enum.Enum):
    manual = "manual"
    jira = "jira"


class TaskStatus(str, enum.Enum):
    backlog = "backlog"
    active = "active"
    done = "done"
    archived = "archived"


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    source = Column(SAEnum(TaskSource), nullable=False, default=TaskSource.manual)
    external_key = Column(String(100), nullable=True)
    external_url = Column(String(1000), nullable=True)
    status = Column(SAEnum(TaskStatus), nullable=False, default=TaskStatus.backlog)
    priority = Column(SAEnum(Priority), nullable=False, default=Priority.medium)
    due_date = Column(Date, nullable=True)
    estimated_seconds = Column(Integer, nullable=True)
    category = Column(String(100), nullable=True)
    meeting_time = Column(Time, nullable=True)
    reminder_minutes_before = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="tasks")
    project = relationship("Project", back_populates="tasks")
    daily_tasks = relationship("DailyTask", back_populates="task")
    comments = relationship(
        "TaskComment",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskComment.created_at.desc()",
    )
    reminder_deliveries = relationship(
        "TaskReminderDelivery",
        back_populates="task",
        cascade="all, delete-orphan",
    )
