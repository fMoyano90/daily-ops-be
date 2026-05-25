import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.models.project import Base
from app.models.task import Priority


class SubtaskStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"


class DailySubtask(Base):
    __tablename__ = "daily_subtasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    daily_task_id = Column(UUID(as_uuid=True), ForeignKey("daily_tasks.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    status = Column(SAEnum(SubtaskStatus, name="subtaskstatus"), nullable=False, default=SubtaskStatus.pending)
    priority = Column(SAEnum(Priority, name="priority"), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    user = relationship("User", back_populates="daily_subtasks")
    daily_task = relationship("DailyTask", back_populates="subtasks")
