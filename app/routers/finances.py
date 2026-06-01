from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.finance import FinanceEntry
from app.models.user import User
from app.schemas.finance import (
    FinanceEntryCreate,
    FinanceEntryResponse,
    FinanceEntryUpdate,
    FinanceLoanRepaymentCreate,
    FinanceLoanResponse,
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


def _clean_text(value: str | None) -> str | None:
    cleaned = value.strip() if value else None
    return cleaned or None


def _normalize_entry_data(data: dict) -> dict:
    kind = data.get("kind") or "cash"
    data["kind"] = kind
    data["person"] = _clean_text(data.get("person"))

    if kind == "credit_purchase":
        data["type"] = "expense"
        data["affects_balance"] = False
        data["status"] = data.get("status") or "open"
    elif kind == "loan_given":
        if not data.get("person"):
            raise HTTPException(status_code=400, detail="Person is required for loans")
        data["type"] = "expense"
        data["affects_balance"] = True
        data["status"] = data.get("status") or "open"
    elif kind == "loan_repayment":
        data["type"] = "income"
        data["affects_balance"] = True
        data["status"] = data.get("status") or "posted"
    else:
        data["kind"] = "cash"
        if data.get("affects_balance") is None:
            data["affects_balance"] = True
        data["status"] = data.get("status") or "posted"

    return data


async def _loan_response(db: AsyncSession, loan: FinanceEntry) -> FinanceLoanResponse:
    result = await db.execute(
        select(FinanceEntry).where(
            FinanceEntry.linked_entry_id == loan.id,
            FinanceEntry.kind == "loan_repayment",
            FinanceEntry.status != "cancelled",
        )
    )
    repayments = result.scalars().all()
    repaid_amount = sum(entry.amount for entry in repayments) or Decimal("0.00")
    pending_amount = max(loan.amount - repaid_amount, Decimal("0.00"))
    return FinanceLoanResponse(
        id=loan.id,
        date=loan.date,
        person=loan.person or "Sin nombre",
        amount=loan.amount,
        repaid_amount=repaid_amount,
        pending_amount=pending_amount,
        due_date=loan.due_date,
        status="paid" if pending_amount <= 0 else loan.status,
        description=loan.description,
        created_at=loan.created_at,
        updated_at=loan.updated_at,
    )


@router.get("/entries", response_model=list[FinanceEntryResponse])
async def list_entries(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    type: str | None = Query(None),
    kind: str | None = Query(None),
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
    if kind in ("cash", "credit_purchase", "loan_given", "loan_repayment"):
        query = query.where(FinanceEntry.kind == kind)
    result = await db.execute(query.order_by(FinanceEntry.date.desc(), FinanceEntry.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.post("/entries", response_model=FinanceEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(
    data: FinanceEntryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = FinanceEntry(user_id=user.id, **_normalize_entry_data(data.model_dump()))
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
    update_data = data.model_dump(exclude_unset=True)
    merged = {
        "date": entry.date,
        "type": entry.type,
        "kind": entry.kind,
        "amount": entry.amount,
        "category": entry.category,
        "description": entry.description,
        "affects_balance": entry.affects_balance,
        "person": entry.person,
        "due_date": entry.due_date,
        "status": entry.status,
        "linked_entry_id": entry.linked_entry_id,
        **update_data,
    }
    normalized = _normalize_entry_data(merged)
    fields_to_apply = set(update_data)
    if "kind" in update_data:
        fields_to_apply.update({"type", "affects_balance", "status"})
    for key in fields_to_apply:
        value = normalized[key]
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
        select(FinanceEntry).where(FinanceEntry.user_id == user.id, FinanceEntry.date <= date)
    )
    entries = result.scalars().all()
    balance_entries = [entry for entry in entries if entry.affects_balance]
    previous_entries = [entry for entry in balance_entries if entry.date < date]
    current_entries = [entry for entry in balance_entries if entry.date == date]
    total_income = sum(e.amount for e in current_entries if e.type == "income") or Decimal("0.00")
    total_expense = sum(e.amount for e in current_entries if e.type == "expense") or Decimal("0.00")
    opening_income = sum(e.amount for e in previous_entries if e.type == "income") or Decimal("0.00")
    opening_expense = sum(e.amount for e in previous_entries if e.type == "expense") or Decimal("0.00")
    opening_balance = opening_income - opening_expense
    daily_balance = total_income - total_expense
    credit_pending = sum(e.amount for e in entries if e.kind == "credit_purchase" and e.status == "open") or Decimal("0.00")

    loan_results = await db.execute(
        select(FinanceEntry).where(
            FinanceEntry.user_id == user.id,
            FinanceEntry.kind == "loan_given",
            FinanceEntry.status != "cancelled",
        )
    )
    loans = loan_results.scalars().all()
    loans_pending = Decimal("0.00")
    for loan in loans:
        loan_summary = await _loan_response(db, loan)
        if loan_summary.status != "paid":
            loans_pending += loan_summary.pending_amount

    return FinanceSummaryResponse(
        date=date,
        total_income=total_income,
        total_expense=total_expense,
        opening_balance=opening_balance,
        daily_balance=daily_balance,
        balance=opening_balance + daily_balance,
        credit_pending=credit_pending,
        loans_pending=loans_pending,
    )


@router.get("/credit-purchases", response_model=list[FinanceEntryResponse])
async def list_credit_purchases(
    status: str | None = Query("open"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(FinanceEntry).where(
        FinanceEntry.user_id == user.id,
        FinanceEntry.kind == "credit_purchase",
    )
    if status in ("open", "paid", "cancelled"):
        query = query.where(FinanceEntry.status == status)
    result = await db.execute(query.order_by(FinanceEntry.date.desc(), FinanceEntry.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.get("/loans", response_model=list[FinanceLoanResponse])
async def list_loans(
    status: str | None = Query("open"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(FinanceEntry).where(
        FinanceEntry.user_id == user.id,
        FinanceEntry.kind == "loan_given",
    )
    if status in ("open", "paid", "cancelled"):
        query = query.where(FinanceEntry.status == status)
    result = await db.execute(query.order_by(FinanceEntry.date.desc(), FinanceEntry.created_at.desc()).limit(limit))
    loans = result.scalars().all()
    return [await _loan_response(db, loan) for loan in loans]


@router.post("/loans/{loan_id}/repay", response_model=FinanceLoanResponse, status_code=status.HTTP_201_CREATED)
async def repay_loan(
    loan_id: UUID,
    data: FinanceLoanRepaymentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    loan = await _get_entry_or_404(db, user, loan_id)
    if loan.kind != "loan_given":
        raise HTTPException(status_code=400, detail="Entry is not a loan")
    if loan.status == "cancelled":
        raise HTTPException(status_code=400, detail="Loan is cancelled")

    repayment = FinanceEntry(
        user_id=user.id,
        date=data.date,
        type="income",
        kind="loan_repayment",
        amount=data.amount,
        category="Devolucion prestamo",
        description=data.description,
        affects_balance=True,
        person=loan.person,
        status="posted",
        linked_entry_id=loan.id,
    )
    db.add(repayment)
    await db.flush()

    loan_summary = await _loan_response(db, loan)
    if loan_summary.pending_amount <= 0:
        loan.status = "paid"
        await db.flush()
        await db.refresh(loan)
        loan_summary = await _loan_response(db, loan)

    return loan_summary
