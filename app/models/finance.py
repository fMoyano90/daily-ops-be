import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.project import Base


class FinanceEntry(Base):
    __tablename__ = "finance_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    type = Column(String(10), nullable=False)  # "income" | "expense"
    kind = Column(String(20), nullable=False, default="cash")
    amount = Column(Numeric(12, 2), nullable=False)
    category = Column(String(80), nullable=False)
    description = Column(Text, nullable=True)
    affects_balance = Column(Boolean, nullable=False, default=True)
    person = Column(String(120), nullable=True)
    due_date = Column(Date, nullable=True)
    status = Column(String(20), nullable=False, default="posted")
    linked_entry_id = Column(UUID(as_uuid=True), ForeignKey("finance_entries.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="finance_entries")
