import uuid
from datetime import datetime, date

from sqlalchemy import Column, String, Text, DateTime, Date, Enum as SAEnum, ForeignKey, Integer, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.models.project import Base


class GoalHorizon(str, enum.Enum):
    short = "short"
    medium = "medium"
    long = "long"


class GoalStatus(str, enum.Enum):
    active = "active"
    achieved = "achieved"
    paused = "paused"
    abandoned = "abandoned"


class GoalStepStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    blocked = "blocked"


class Goal(Base):
    __tablename__ = "goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    horizon = Column(SAEnum(GoalHorizon), nullable=False, default=GoalHorizon.medium)
    status = Column(SAEnum(GoalStatus), nullable=False, default=GoalStatus.active)
    progress = Column(Float, default=0.0, nullable=False)
    start_date = Column(Date, nullable=False)
    target_date = Column(Date, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    anti_goals = Column(Text, nullable=True)
    key_results = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="goals")
    project = relationship("Project", back_populates="goals")
    steps = relationship("GoalStep", back_populates="goal", cascade="all, delete-orphan", order_by="GoalStep.sort_order")
    comments = relationship("GoalComment", back_populates="goal", cascade="all, delete-orphan", order_by="GoalComment.created_at.desc()")


class GoalStep(Base):
    __tablename__ = "goal_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    status = Column(SAEnum(GoalStepStatus), nullable=False, default=GoalStepStatus.pending)
    sort_order = Column(Integer, default=0, nullable=False)
    linked_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    goal = relationship("Goal", back_populates="steps")
    linked_task = relationship("Task", foreign_keys=[linked_task_id])


class GoalComment(Base):
    __tablename__ = "goal_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="goal_comments")
    goal = relationship("Goal", back_populates="comments")
