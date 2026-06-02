import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Column, DateTime, Date, Enum as SAEnum, Float, ForeignKey, Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from app.models.project import Base


class CaptureType(str, enum.Enum):
    text = "text"
    url = "url"
    image = "image"
    voice = "voice"
    mixed = "mixed"


class CaptureStatus(str, enum.Enum):
    inbox = "inbox"
    reviewed = "reviewed"
    converted = "converted"
    archived = "archived"


class Capture(Base):
    __tablename__ = "captures"
    __table_args__ = (
        Index("ix_captures_user_status", "user_id", "status"),
        Index("ix_captures_user_type", "user_id", "capture_type"),
        Index("ix_captures_user_date", "user_id", "note_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=True)
    content = Column(Text, nullable=True)
    capture_type = Column(SAEnum(CaptureType), nullable=False, default=CaptureType.text)
    source_url = Column(Text, nullable=True)
    status = Column(SAEnum(CaptureStatus), nullable=False, default=CaptureStatus.inbox)
    tags = Column(ARRAY(String), nullable=False, default=list)
    note_date = Column(Date, nullable=False)
    transcript = Column(Text, nullable=True)
    converted_task_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="captures")
    attachments = relationship("CaptureAttachment", back_populates="capture", cascade="all, delete-orphan", order_by="CaptureAttachment.created_at.asc()")


class CaptureAttachment(Base):
    __tablename__ = "capture_attachments"
    __table_args__ = (
        Index("ix_capture_attachments_capture", "capture_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    capture_id = Column(UUID(as_uuid=True), ForeignKey("captures.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(20), nullable=False)  # "image" | "audio"
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(120), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    storage_path = Column(String(500), nullable=False)
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="capture_attachments")
    capture = relationship("Capture", back_populates="attachments")
