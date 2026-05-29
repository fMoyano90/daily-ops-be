import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, Date, DateTime, Float, ForeignKey, Integer, Text, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.project import Base


class SleepLog(Base):
    __tablename__ = "sleep_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_sleep_logs_user_date"),
        CheckConstraint("hours_slept IS NULL OR (hours_slept >= 0 AND hours_slept <= 24)", name="ck_sleep_logs_hours_slept"),
        CheckConstraint("sleep_quality IS NULL OR (sleep_quality >= 1 AND sleep_quality <= 10)", name="ck_sleep_logs_sleep_quality"),
        CheckConstraint("wakeups IS NULL OR (wakeups >= 0 AND wakeups <= 50)", name="ck_sleep_logs_wakeups"),
        CheckConstraint(
            "tiredness_on_wake IS NULL OR (tiredness_on_wake >= 1 AND tiredness_on_wake <= 10)",
            name="ck_sleep_logs_tiredness_on_wake",
        ),
        CheckConstraint(
            "tiredness_during_day IS NULL OR (tiredness_during_day >= 1 AND tiredness_during_day <= 10)",
            name="ck_sleep_logs_tiredness_during_day",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    daily_plan_id = Column(UUID(as_uuid=True), ForeignKey("daily_plans.id", ondelete="SET NULL"), nullable=True)
    date = Column(Date, nullable=False)
    hours_slept = Column(Float, nullable=True)
    sleep_quality = Column(Integer, nullable=True)
    bedtime = Column(Time, nullable=True)
    wake_time = Column(Time, nullable=True)
    wakeups = Column(Integer, nullable=True)
    tiredness_on_wake = Column(Integer, nullable=True)
    tiredness_during_day = Column(Integer, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="sleep_logs")
    daily_plan = relationship("DailyPlan", back_populates="sleep_log")
