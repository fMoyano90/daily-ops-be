from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.finance import FinanceEntry
from app.models.user import User
from app.schemas.finance import (
    FinanceEntryCreate,
    FinanceEntryResponse,
    FinanceEntryUpdate,
    FinanceSummaryResponse,
)

router = APIRouter(prefix="/api/v1/finances", tags=["finances"])


async def _get_entry_or_404(db: AsyncSession, user: User, entry_id: UUID) -> FinanceEntry:
    result = await db.execute(
        select(FinanceEntry).where(FinanceEntry.id == entry_id, FinanceEntry.user_id == user.id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Finance entry not found")
    return entry


@router.get("/entries", response_model=list[FinanceEntryResponse])
async def list_entries(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    type: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(FinanceEntry).where(FinanceEntry.user_id == user.id)
    if date_from:
        query = query.where(FinanceEntry.date >= date_from)
    if date_to:
        query = query.where(FinanceEntry.date <= date_to)
    if type in ("income", "expense"):
        query = query.where(FinanceEntry.type == type)
    result = await db.execute(query.order_by(FinanceEntry.date.desc(), FinanceEntry.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.post("/entries", response_model=FinanceEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(
    data: FinanceEntryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = FinanceEntry(user_id=user.id, **data.model_dump())
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


@router.patch("/entries/{entry_id}", response_model=FinanceEntryResponse)
async def update_entry(
    entry_id: UUID,
    data: FinanceEntryUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = await _get_entry_or_404(db, user, entry_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    await db.flush()
    await db.refresh(entry)
    return entry


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = await _get_entry_or_404(db, user, entry_id)
    await db.delete(entry)
    await db.flush()


@router.get("/summary", response_model=FinanceSummaryResponse)
async def get_daily_summary(
    date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FinanceEntry).where(FinanceEntry.user_id == user.id, FinanceEntry.date == date)
    )
    entries = result.scalars().all()
    total_income = sum(e.amount for e in entries if e.type == "income") or Decimal("0.00")
    total_expense = sum(e.amount for e in entries if e.type == "expense") or Decimal("0.00")
    return FinanceSummaryResponse(
        date=date,
        total_income=total_income,
        total_expense=total_expense,
        balance=total_income - total_expense,
    )
