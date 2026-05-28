from collections import Counter
from datetime import datetime, time, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.daily_plan import DailyPlan
from app.models.daily_task import DailyTask
from app.models.emotion import EmotionEntry, EmotionValence
from app.models.project import Project
from app.models.user import User
from app.schemas.emotion import EmotionEntryCreate, EmotionEntryResponse, EmotionEntryUpdate, EmotionSummaryResponse
from app.utils.timezone import app_tz, local_today

router = APIRouter(prefix="/api/v1/emotions", tags=["emotions"])


def _date_bounds(start_date, end_date):
    tz = app_tz()
    start = datetime.combine(start_date, time.min, tzinfo=tz)
    end = datetime.combine(end_date, time.max, tzinfo=tz)
    return start, end


async def _get_entry_or_404(db: AsyncSession, user: User, entry_id: UUID) -> EmotionEntry:
    result = await db.execute(select(EmotionEntry).where(EmotionEntry.id == entry_id, EmotionEntry.user_id == user.id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Emotion entry not found")
    return entry


async def _validate_optional_relations(db: AsyncSession, user: User, data: dict) -> None:
    daily_plan_id = data.get("daily_plan_id")
    daily_task_id = data.get("daily_task_id")
    project_id = data.get("project_id")

    if daily_plan_id:
        result = await db.execute(select(DailyPlan).where(DailyPlan.id == daily_plan_id, DailyPlan.user_id == user.id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Daily plan not found")
    if daily_task_id:
        result = await db.execute(select(DailyTask).where(DailyTask.id == daily_task_id, DailyTask.user_id == user.id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Daily task not found")
    if project_id:
        result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == user.id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Project not found")


def _build_summary(entries: list[EmotionEntry], start_date, end_date) -> EmotionSummaryResponse:
    emotions = Counter(e.emotion for e in entries)
    triggers = Counter(e.trigger_type for e in entries if e.trigger_type)
    valences = Counter(e.valence.value for e in entries)
    total = len(entries)
    avg = round(sum(e.intensity for e in entries) / total, 1) if total else 0.0
    return EmotionSummaryResponse(
        start_date=start_date,
        end_date=end_date,
        total_entries=total,
        average_intensity=avg,
        dominant_emotion=emotions.most_common(1)[0][0] if emotions else None,
        dominant_trigger=triggers.most_common(1)[0][0] if triggers else None,
        unpleasant_count=valences.get(EmotionValence.unpleasant.value, 0),
        pleasant_count=valences.get(EmotionValence.pleasant.value, 0),
        neutral_count=valences.get(EmotionValence.neutral.value, 0),
        by_emotion=dict(emotions.most_common()),
        by_trigger=dict(triggers.most_common()),
        by_valence=dict(valences.most_common()),
    )


@router.get("/today", response_model=list[EmotionEntryResponse])
async def list_today_emotions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = local_today()
    start, end = _date_bounds(today, today)
    result = await db.execute(
        select(EmotionEntry)
        .where(EmotionEntry.user_id == user.id, EmotionEntry.occurred_at >= start, EmotionEntry.occurred_at <= end)
        .order_by(EmotionEntry.occurred_at.desc())
    )
    return result.scalars().all()


@router.get("/summary/week", response_model=EmotionSummaryResponse)
async def weekly_summary(
    week_start: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if week_start:
        start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
    else:
        today = local_today()
        start_date = today - timedelta(days=today.weekday())
    end_date = start_date + timedelta(days=6)
    start, end = _date_bounds(start_date, end_date)
    result = await db.execute(
        select(EmotionEntry)
        .where(EmotionEntry.user_id == user.id, EmotionEntry.occurred_at >= start, EmotionEntry.occurred_at <= end)
        .order_by(EmotionEntry.occurred_at.asc())
    )
    return _build_summary(result.scalars().all(), start_date, end_date)


@router.get("", response_model=list[EmotionEntryResponse])
async def list_emotions(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    emotion: str | None = Query(None),
    valence: EmotionValence | None = Query(None),
    trigger_type: str | None = Query(None),
    project_id: UUID | None = Query(None),
    min_intensity: int | None = Query(None, ge=1, le=10),
    limit: int = Query(60, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(EmotionEntry).where(EmotionEntry.user_id == user.id)
    if date_from or date_to:
        start_date = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else local_today() - timedelta(days=30)
        end_date = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else local_today()
        start, end = _date_bounds(start_date, end_date)
        query = query.where(EmotionEntry.occurred_at >= start, EmotionEntry.occurred_at <= end)
    if emotion:
        query = query.where(EmotionEntry.emotion == emotion)
    if valence:
        query = query.where(EmotionEntry.valence == valence)
    if trigger_type:
        query = query.where(EmotionEntry.trigger_type == trigger_type)
    if project_id:
        query = query.where(EmotionEntry.project_id == project_id)
    if min_intensity:
        query = query.where(EmotionEntry.intensity >= min_intensity)

    result = await db.execute(query.order_by(EmotionEntry.occurred_at.desc()).limit(limit))
    return result.scalars().all()


@router.post("", response_model=EmotionEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_emotion(
    data: EmotionEntryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    payload = data.model_dump(exclude_unset=True)
    await _validate_optional_relations(db, user, payload)
    entry = EmotionEntry(user_id=user.id, **payload)
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


@router.get("/{entry_id}", response_model=EmotionEntryResponse)
async def get_emotion(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _get_entry_or_404(db, user, entry_id)


@router.patch("/{entry_id}", response_model=EmotionEntryResponse)
async def update_emotion(
    entry_id: UUID,
    data: EmotionEntryUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = await _get_entry_or_404(db, user, entry_id)
    payload = data.model_dump(exclude_unset=True)
    await _validate_optional_relations(db, user, payload)
    for key, value in payload.items():
        setattr(entry, key, value)
    await db.flush()
    await db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_emotion(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = await _get_entry_or_404(db, user, entry_id)
    await db.delete(entry)
    await db.flush()
