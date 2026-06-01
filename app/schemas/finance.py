from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


FinanceEntryKind = Literal["cash", "credit_purchase", "loan_given", "loan_repayment"]
FinanceEntryStatus = Literal["posted", "open", "paid", "cancelled"]


class FinanceEntryCreate(BaseModel):
    date: date_type
    type: Literal["income", "expense"]
    kind: FinanceEntryKind = "cash"
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    category: str = Field(min_length=1, max_length=80)
    description: Optional[str] = None
    affects_balance: Optional[bool] = None
    person: Optional[str] = Field(default=None, max_length=120)
    due_date: Optional[date_type] = None
    status: Optional[FinanceEntryStatus] = None
    linked_entry_id: Optional[UUID] = None


class FinanceEntryUpdate(BaseModel):
    date: Optional[date_type] = None
    type: Optional[Literal["income", "expense"]] = None
    kind: Optional[FinanceEntryKind] = None
    amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    category: Optional[str] = Field(default=None, min_length=1, max_length=80)
    description: Optional[str] = None
    affects_balance: Optional[bool] = None
    person: Optional[str] = Field(default=None, max_length=120)
    due_date: Optional[date_type] = None
    status: Optional[FinanceEntryStatus] = None
    linked_entry_id: Optional[UUID] = None


class FinanceLoanRepaymentCreate(BaseModel):
    date: date_type
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: Optional[str] = None


class FinanceEntryResponse(BaseModel):
    id: UUID
    date: date_type
    type: str
    kind: str
    amount: Decimal
    category: str
    description: Optional[str] = None
    affects_balance: bool
    person: Optional[str] = None
    due_date: Optional[date_type] = None
    status: str
    linked_entry_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FinanceSummaryResponse(BaseModel):
    date: date_type
    total_income: Decimal
    total_expense: Decimal
    opening_balance: Decimal
    daily_balance: Decimal
    balance: Decimal
    credit_pending: Decimal
    loans_pending: Decimal


class FinanceLoanResponse(BaseModel):
    id: UUID
    date: date_type
    person: str
    amount: Decimal
    repaid_amount: Decimal
    pending_amount: Decimal
    due_date: Optional[date_type] = None
    status: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
