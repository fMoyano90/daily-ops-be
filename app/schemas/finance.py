from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class FinanceEntryCreate(BaseModel):
    date: date
    type: Literal["income", "expense"]
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    category: str = Field(min_length=1, max_length=80)
    description: Optional[str] = None


class FinanceEntryUpdate(BaseModel):
    date: Optional[date] = None
    type: Optional[Literal["income", "expense"]] = None
    amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    category: Optional[str] = Field(default=None, min_length=1, max_length=80)
    description: Optional[str] = None


class FinanceEntryResponse(BaseModel):
    id: UUID
    date: date
    type: str
    amount: Decimal
    category: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FinanceSummaryResponse(BaseModel):
    date: date
    total_income: Decimal
    total_expense: Decimal
    balance: Decimal
