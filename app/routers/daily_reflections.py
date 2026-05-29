from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.daily_plan import DailyPlan
from app.models.daily_reflection import DailyReflection
from app.models.user import User
from app.schemas.daily_reflection import DailyReflectionResponse, DailyReflectionSummaryResponse, DailyReflectionUpdate
from app.utils.timezone import local_today

router = APIRouter(prefix="/api/v1/daily-reflections", tags=["daily-reflections"])


def _avg(values: list[int | None]) -> float | None:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 1)


def _trend(values: list[int | None]) -> str:
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


async def _get_reflection_or_404(db: AsyncSession, user: User, reflection_id: UUID) -> DailyReflection:
    result = await db.execute(
        select(DailyReflection)
        .where(DailyReflection.id == reflection_id, DailyReflection.user_id == user.id)
        .options(selectinload(DailyReflection.daily_plan))
    )
    reflection = result.scalar_one_or_none()
    if not reflection:
        raise HTTPException(status_code=404, detail="Daily reflection not found")
    return reflection


@router.get("/today", response_model=DailyReflectionResponse | None)
async def get_today_reflection(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = local_today()
    result = await db.execute(
        select(DailyReflection)
        .join(DailyPlan, DailyPlan.id == DailyReflection.daily_plan_id, isouter=True)
        .where(DailyReflection.user_id == user.id)
        .where(DailyPlan.date == today)
    )
    return result.scalar_one_or_none()


@router.get("", response_model=list[DailyReflectionResponse])
async def list_reflections(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(DailyReflection)
        .where(DailyReflection.user_id == user.id)
        .options(selectinload(DailyReflection.daily_plan))
    )
    joined_plan = False

    if date_from:
        query = query.join(DailyPlan, DailyPlan.id == DailyReflection.daily_plan_id).where(DailyPlan.date >= date_from)
        joined_plan = True
    if date_to:
        if not joined_plan:
            query = query.join(DailyPlan, DailyPlan.id == DailyReflection.daily_plan_id)
            joined_plan = True
        query = query.where(DailyPlan.date <= date_to)

    result = await db.execute(query.order_by(DailyReflection.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.get("/summary/week", response_model=DailyReflectionSummaryResponse)
async def weekly_summary(
    week_start: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = local_today()
    start_date = week_start if week_start else today - timedelta(days=today.weekday())
    end_date = start_date + timedelta(days=6)
    return await _period_summary(db, user, start_date, end_date)


@router.get("/summary/month", response_model=DailyReflectionSummaryResponse)
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


@router.get("/{plan_date}", response_model=DailyReflectionResponse)
async def get_reflection_by_date(
    plan_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DailyReflection)
        .join(DailyPlan, DailyPlan.id == DailyReflection.daily_plan_id)
        .where(DailyReflection.user_id == user.id, DailyPlan.date == plan_date)
    )
    reflection = result.scalar_one_or_none()
    if not reflection:
        raise HTTPException(status_code=404, detail="Daily reflection not found for this date")
    return reflection


@router.patch("/{reflection_id}", response_model=DailyReflectionResponse)
async def update_reflection(
    reflection_id: UUID,
    data: DailyReflectionUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    reflection = await _get_reflection_or_404(db, user, reflection_id)
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        setattr(reflection, key, value)
    await db.flush()
    await db.refresh(reflection)
    return reflection


@router.delete("/{reflection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reflection(
    reflection_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    reflection = await _get_reflection_or_404(db, user, reflection_id)
    await db.delete(reflection)
    await db.flush()


async def _period_summary(
    db: AsyncSession,
    user: User,
    start_date: date,
    end_date: date,
) -> DailyReflectionSummaryResponse:
    result = await db.execute(
        select(DailyReflection)
        .join(DailyPlan, DailyPlan.id == DailyReflection.daily_plan_id)
        .where(DailyReflection.user_id == user.id, DailyPlan.date >= start_date, DailyPlan.date <= end_date)
        .order_by(DailyPlan.date.asc())
    )
    reflections = result.scalars().all()
    period_days = (end_date - start_date).days + 1
    mood_values = [r.mood_rating for r in reflections]
    energy_values = [r.energy_rating for r in reflections]
    productivity_values = [r.productivity_rating for r in reflections]

    return DailyReflectionSummaryResponse(
        period_start=start_date,
        period_end=end_date,
        total_reflections=len(reflections),
        days_with_reflection=len(reflections),
        days_without_reflection=max(period_days - len(reflections), 0),
        avg_mood=_avg(mood_values),
        avg_energy=_avg(energy_values),
        avg_productivity=_avg(productivity_values),
        mood_trend=_trend(mood_values),
        energy_trend=_trend(energy_values),
        productivity_trend=_trend(productivity_values),
    )
