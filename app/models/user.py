import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.project import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    daily_plans = relationship("DailyPlan", back_populates="user", cascade="all, delete-orphan")
    daily_tasks = relationship("DailyTask", back_populates="user", cascade="all, delete-orphan")
    daily_subtasks = relationship("DailySubtask", back_populates="user", cascade="all, delete-orphan")
    timer_sessions = relationship("TimerSession", back_populates="user", cascade="all, delete-orphan")
    recurring_tasks = relationship("RecurringTask", back_populates="user", cascade="all, delete-orphan")
    jira_connections = relationship("JiraConnection", back_populates="user", cascade="all, delete-orphan")
    task_comments = relationship("TaskComment", back_populates="user", cascade="all, delete-orphan")
    push_subscriptions = relationship("PushSubscription", back_populates="user", cascade="all, delete-orphan")
    reminder_deliveries = relationship("TaskReminderDelivery", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    goal_comments = relationship("GoalComment", back_populates="user", cascade="all, delete-orphan")
    emotion_entries = relationship("EmotionEntry", back_populates="user", cascade="all, delete-orphan")
    daily_reflections = relationship("DailyReflection", back_populates="user", cascade="all, delete-orphan")
