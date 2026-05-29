from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.daily_plan import DailyPlan
from app.models.sleep_log import SleepLog
from app.models.user import User
from app.schemas.sleep_log import SleepLogCreate, SleepLogResponse, SleepLogSummaryResponse, SleepLogUpdate
from app.utils.timezone import local_today

router = APIRouter(prefix="/api/v1/sleep-logs", tags=["sleep-logs"])


def _avg(values: list[int | float | None]) -> float | None:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 1)


def _trend(values: list[int | float | None]) -> str:
    valid = [v for v in values if v is not None]
    if len(valid) < 2:
        return "stable"

    midpoint = len(valid) // 2
    first_half = valid[:midpoint]
    second_half = valid[midpoint:]
    if not first_half or not second_half:
        return "stable"

    first_avg = sum(first_half) / len(first_half)
    second_avg = sum(second_half) / len(second_half)
    delta = second_avg - first_avg
    if delta > 0.25:
        return "up"
    if delta < -0.25:
        return "down"
    return "stable"


async def _get_sleep_log_or_404(db: AsyncSession, user: User, sleep_log_id: UUID) -> SleepLog:
    result = await db.execute(
        select(SleepLog)
        .where(SleepLog.id == sleep_log_id, SleepLog.user_id == user.id)
        .options(selectinload(SleepLog.daily_plan))
    )
    sleep_log = result.scalar_one_or_none()
    if not sleep_log:
        raise HTTPException(status_code=404, detail="Sleep log not found")
    return sleep_log


async def _find_plan_for_date(db: AsyncSession, user: User, log_date: date) -> DailyPlan | None:
    result = await db.execute(select(DailyPlan).where(DailyPlan.user_id == user.id, DailyPlan.date == log_date))
    return result.scalar_one_or_none()


@router.get("/today", response_model=SleepLogResponse | None)
async def get_today_sleep_log(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = local_today()
    result = await db.execute(select(SleepLog).where(SleepLog.user_id == user.id, SleepLog.date == today))
    return result.scalar_one_or_none()


@router.get("", response_model=list[SleepLogResponse])
async def list_sleep_logs(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(SleepLog).where(SleepLog.user_id == user.id)
    if date_from:
        query = query.where(SleepLog.date >= date_from)
    if date_to:
        query = query.where(SleepLog.date <= date_to)

    result = await db.execute(query.order_by(SleepLog.date.desc()).limit(limit))
    return result.scalars().all()


@router.post("", response_model=SleepLogResponse, status_code=status.HTTP_201_CREATED)
async def create_sleep_log(
    data: SleepLogCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    log_date = data.date or local_today()
    existing_result = await db.execute(select(SleepLog).where(SleepLog.user_id == user.id, SleepLog.date == log_date))
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Sleep log already exists for this date")

    plan = await _find_plan_for_date(db, user, log_date)
    payload = data.model_dump(exclude={"date"}, exclude_unset=True)
    sleep_log = SleepLog(user_id=user.id, daily_plan_id=plan.id if plan else None, date=log_date, **payload)
    db.add(sleep_log)
    await db.flush()
    await db.refresh(sleep_log)
    return sleep_log


@router.get("/summary/week", response_model=SleepLogSummaryResponse)
async def weekly_summary(
    week_start: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = local_today()
    start_date = week_start if week_start else today - timedelta(days=today.weekday())
    end_date = start_date + timedelta(days=6)
    return await _period_summary(db, user, start_date, end_date)


@router.get("/summary/month", response_model=SleepLogSummaryResponse)
async def monthly_summary(
    month: str | None = Query(None, description="YYYY-MM"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if month:
        try:
            start_date = datetime.strptime(month + "-01", "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="month must be in YYYY-MM format") from exc
    else:
        today = local_today()
        start_date = today.replace(day=1)

    if start_date.month == 12:
        next_month = start_date.replace(year=start_date.year + 1, month=1, day=1)
    else:
        next_month = start_date.replace(month=start_date.month + 1, day=1)
    end_date = next_month - timedelta(days=1)

    return await _period_summary(db, user, start_date, end_date)


@router.get("/{log_date}", response_model=SleepLogResponse)
async def get_sleep_log_by_date(
    log_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(SleepLog).where(SleepLog.user_id == user.id, SleepLog.date == log_date))
    sleep_log = result.scalar_one_or_none()
    if not sleep_log:
        raise HTTPException(status_code=404, detail="Sleep log not found for this date")
    return sleep_log


@router.patch("/{sleep_log_id}", response_model=SleepLogResponse)
async def update_sleep_log(
    sleep_log_id: UUID,
    data: SleepLogUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sleep_log = await _get_sleep_log_or_404(db, user, sleep_log_id)
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        setattr(sleep_log, key, value)
    await db.flush()
    await db.refresh(sleep_log)
    return sleep_log


@router.delete("/{sleep_log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sleep_log(
    sleep_log_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sleep_log = await _get_sleep_log_or_404(db, user, sleep_log_id)
    await db.delete(sleep_log)
    await db.flush()


async def _period_summary(
    db: AsyncSession,
    user: User,
    start_date: date,
    end_date: date,
) -> SleepLogSummaryResponse:
    result = await db.execute(
        select(SleepLog)
        .where(SleepLog.user_id == user.id, SleepLog.date >= start_date, SleepLog.date <= end_date)
        .order_by(SleepLog.date.asc())
    )
    logs = result.scalars().all()
    period_days = (end_date - start_date).days + 1

    return SleepLogSummaryResponse(
        period_start=start_date,
        period_end=end_date,
        total_logs=len(logs),
        days_with_log=len(logs),
        days_without_log=max(period_days - len(logs), 0),
        avg_hours_slept=_avg([log.hours_slept for log in logs]),
        avg_sleep_quality=_avg([log.sleep_quality for log in logs]),
        avg_wakeups=_avg([log.wakeups for log in logs]),
        avg_tiredness_on_wake=_avg([log.tiredness_on_wake for log in logs]),
        avg_tiredness_during_day=_avg([log.tiredness_during_day for log in logs]),
        hours_trend=_trend([log.hours_slept for log in logs]),
        quality_trend=_trend([log.sleep_quality for log in logs]),
    )
