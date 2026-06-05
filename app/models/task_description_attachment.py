import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.project import Base


class TaskDescriptionAttachment(Base):
    __tablename__ = "task_description_attachments"
    __table_args__ = (
        CheckConstraint(
            "(task_id IS NOT NULL AND recurring_task_id IS NULL) OR (task_id IS NULL AND recurring_task_id IS NOT NULL)",
            name="ck_task_description_attachment_single_owner",
        ),
        Index("ix_task_description_attachments_task", "task_id"),
        Index("ix_task_description_attachments_recurring", "recurring_task_id"),
        Index("ix_task_description_attachments_user", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    recurring_task_id = Column(UUID(as_uuid=True), ForeignKey("recurring_tasks.id", ondelete="CASCADE"), nullable=True)
    kind = Column(String(20), nullable=False, default="image")
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(120), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    storage_path = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="task_description_attachments")
    task = relationship("Task", back_populates="description_attachments")
    recurring_task = relationship("RecurringTask", back_populates="description_attachments")
