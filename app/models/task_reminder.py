import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.project import Base


class TaskReminderDelivery(Base):
    __tablename__ = "task_reminder_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    recurring_task_id = Column(UUID(as_uuid=True), ForeignKey("recurring_tasks.id", ondelete="CASCADE"), nullable=True)
    reminder_date = Column(DateTime(timezone=True), nullable=False)
    minutes_before = Column(Integer, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="reminder_deliveries")
    task = relationship("Task", back_populates="reminder_deliveries")
    recurring_task = relationship("RecurringTask", back_populates="reminder_deliveries")
