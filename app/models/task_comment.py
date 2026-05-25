import uuid
from datetime import datetime

from sqlalchemy import Column, Text, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.project import Base


class TaskComment(Base):
    __tablename__ = "task_comments"
    __table_args__ = (
        CheckConstraint(
            "(task_id IS NOT NULL)::int + (recurring_task_id IS NOT NULL)::int = 1",
            name="ck_task_comment_owner_exactly_one",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    recurring_task_id = Column(UUID(as_uuid=True), ForeignKey("recurring_tasks.id", ondelete="CASCADE"), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    task = relationship("Task", back_populates="comments")
    recurring_task = relationship("RecurringTask", back_populates="comments")
