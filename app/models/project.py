import uuid
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
import enum

Base = declarative_base()


class ProjectType(str, enum.Enum):
    work = "work"
    business = "business"
    partner = "partner"
    personal = "personal"


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    type = Column(SAEnum(ProjectType), nullable=False)
    color = Column(String(7), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    recurring_tasks = relationship("RecurringTask", back_populates="project", cascade="all, delete-orphan")
