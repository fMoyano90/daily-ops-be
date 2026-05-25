import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Enum as SAEnum, ForeignKey, Boolean, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.models.project import Base
from app.models.task import Priority


class RecurringTaskType(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class RecurringInstanceStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    skipped = "skipped"


class RecurringTask(Base):
    __tablename__ = "recurring_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(SAEnum(Priority, name="priority"), nullable=False, default=Priority.medium)
    category = Column(String(100), nullable=True)
    recurrence_type = Column(SAEnum(RecurringTaskType), nullable=False)
    recurrence_days = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="recurring_tasks")
    instances = relationship("RecurringTaskInstance", back_populates="recurring_task", cascade="all, delete-orphan")
    comments = relationship(
        "TaskComment",
        back_populates="recurring_task",
        cascade="all, delete-orphan",
        order_by="TaskComment.created_at.desc()",
    )


class RecurringTaskInstance(Base):
    __tablename__ = "recurring_task_instances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recurring_task_id = Column(UUID(as_uuid=True), ForeignKey("recurring_tasks.id", ondelete="CASCADE"), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    daily_task_id = Column(UUID(as_uuid=True), ForeignKey("daily_tasks.id", ondelete="SET NULL"), nullable=True)
    status = Column(SAEnum(RecurringInstanceStatus), nullable=False, default=RecurringInstanceStatus.pending)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    recurring_task = relationship("RecurringTask", back_populates="instances")
    daily_task = relationship("DailyTask")
