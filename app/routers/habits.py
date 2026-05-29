from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.emotion import EmotionEntry, EmotionEnergy, EmotionValence
from app.models.habit import Habit, HabitEvent, HabitEventType, HabitStatus, HabitTrackingMode
from app.models.user import User
from app.schemas.habit import (
    HabitCreate,
    HabitEventCreate,
    HabitEventResponse,
    HabitEventUpdate,
    HabitMetrics,
    HabitResponse,
    HabitSummaryResponse,
    HabitUpdate,
)
from app.utils.timezone import app_tz, local_today

router = APIRouter(prefix="/api/v1/habits", tags=["habits"])


def _date_bounds(start_date: date, end_date: date):
    tz = app_tz()
    start = datetime.combine(start_date, time.min, tzinfo=tz)
    end = datetime.combine(end_date, time.max, tzinfo=tz)
    return start, end


async def _get_habit_or_404(db: AsyncSession, user: User, habit_id: UUID) -> Habit:
    result = await db.execute(select(Habit).where(Habit.id == habit_id, Habit.user_id == user.id))
    habit = result.scalar_one_or_none()
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    return habit


async def _get_event_or_404(db: AsyncSession, user: User, habit_id: UUID, event_id: UUID) -> HabitEvent:
    result = await db.execute(
        select(HabitEvent).where(
            HabitEvent.id == event_id,
            HabitEvent.habit_id == habit_id,
            HabitEvent.user_id == user.id,
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Habit event not found")
    return event


def _compute_metrics(all_events: list[HabitEvent], start_date: datetime) -> HabitMetrics:
    relapses = [e for e in all_events if e.event_type == HabitEventType.relapse]
    urges = [e for e in all_events if e.event_type == HabitEventType.urge]
    urges_resisted = sum(1 for e in urges if e.resisted is True)

    now = datetime.now(timezone.utc)

    if relapses:
        latest_relapse = max(relapses, key=lambda e: e.occurred_at)
        days_since = (now - latest_relapse.occurred_at).days
    else:
        days_since = (now - start_date).days

    # compute longest streak by walking sorted relapse dates
    longest = 0
    if relapses:
        sorted_relapses = sorted(relapses, key=lambda e: e.occurred_at)
        prev = start_date
        for r in sorted_relapses:
            gap = (r.occurred_at - prev).days
            if gap > longest:
                longest = gap
            prev = r.occurred_at
        # streak from last relapse to now
        gap = (now - prev).days
        if gap > longest:
            longest = gap
    else:
        longest = (now - start_date).days

    return HabitMetrics(
        current_streak_days=days_since,
        longest_streak_days=longest,
        days_since_last_relapse=days_since if relapses else None,
        total_relapses=len(relapses),
        total_urges=len(urges),
        urges_resisted=urges_resisted,
        urge_resistance_rate=round(urges_resisted / len(urges), 2) if urges else 0.0,
    )


def _build_summary(
    events: list[HabitEvent],
    all_events: list[HabitEvent],
    start_date_obj: date,
    end_date_obj: date,
    habit_start: datetime,
) -> HabitSummaryResponse:
    relapses = [e for e in events if e.event_type == HabitEventType.relapse]
    urges = [e for e in events if e.event_type == HabitEventType.urge]
    check_ins = [e for e in events if e.event_type == HabitEventType.check_in]
    urges_resisted = sum(1 for e in urges if e.resisted is True)
    triggers = Counter(e.trigger for e in events if e.trigger)
    emotions = Counter(e.emotion for e in events if e.emotion)
    intensities = [e.intensity for e in events if e.intensity is not None]

    metrics = _compute_metrics(all_events, habit_start)

    return HabitSummaryResponse(
        start_date=start_date_obj,
        end_date=end_date_obj,
        total_events=len(events),
        relapses=len(relapses),
        urges=len(urges),
        check_ins=len(check_ins),
        urges_resisted=urges_resisted,
        urge_resistance_rate=round(urges_resisted / len(urges), 2) if urges else 0.0,
        dominant_trigger=triggers.most_common(1)[0][0] if triggers else None,
        dominant_emotion=emotions.most_common(1)[0][0] if emotions else None,
        avg_intensity=round(sum(intensities) / len(intensities), 1) if intensities else 0.0,
        metrics=metrics,
    )


# ─── Habit CRUD ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[HabitResponse])
async def list_habits(
    status_filter: HabitStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Habit).where(Habit.user_id == user.id)
    if status_filter:
        query = query.where(Habit.status == status_filter)
    result = await db.execute(query.order_by(Habit.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=HabitResponse, status_code=status.HTTP_201_CREATED)
async def create_habit(
    data: HabitCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    payload = data.model_dump(exclude_unset=True)
    habit = Habit(user_id=user.id, **payload)
    db.add(habit)
    await db.flush()
    await db.refresh(habit)
    return habit


@router.get("/{habit_id}", response_model=HabitResponse)
async def get_habit(
    habit_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _get_habit_or_404(db, user, habit_id)


@router.patch("/{habit_id}", response_model=HabitResponse)
async def update_habit(
    habit_id: UUID,
    data: HabitUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    habit = await _get_habit_or_404(db, user, habit_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(habit, key, value)
    await db.flush()
    await db.refresh(habit)
    return habit


@router.delete("/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_habit(
    habit_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    habit = await _get_habit_or_404(db, user, habit_id)
    await db.delete(habit)
    await db.flush()


# ─── Events ──────────────────────────────────────────────────────────────────

@router.get("/{habit_id}/events", response_model=list[HabitEventResponse])
async def list_events(
    habit_id: UUID,
    event_type: HabitEventType | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_habit_or_404(db, user, habit_id)
    query = select(HabitEvent).where(HabitEvent.habit_id == habit_id, HabitEvent.user_id == user.id)
    if event_type:
        query = query.where(HabitEvent.event_type == event_type)
    if date_from or date_to:
        s = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else local_today() - timedelta(days=30)
        e = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else local_today()
        start, end = _date_bounds(s, e)
        query = query.where(HabitEvent.occurred_at >= start, HabitEvent.occurred_at <= end)
    result = await db.execute(query.order_by(HabitEvent.occurred_at.desc()).limit(limit))
    return result.scalars().all()


@router.post("/{habit_id}/events", response_model=HabitEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    habit_id: UUID,
    data: HabitEventCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    habit = await _get_habit_or_404(db, user, habit_id)
    payload = data.model_dump(exclude_unset=True, exclude={"mirror_to_emotions"})

    emotion_entry_id = None
    if data.mirror_to_emotions and data.emotion:
        valence = EmotionValence.unpleasant if data.event_type == HabitEventType.relapse else EmotionValence.neutral
        entry = EmotionEntry(
            user_id=user.id,
            emotion=data.emotion,
            secondary_emotions=[],
            intensity=data.intensity or 5,
            valence=valence,
            energy=EmotionEnergy.medium,
            trigger_type=data.trigger,
            trigger_note=data.feeling_note,
            thought=data.thought,
            note=f"[Hábito: {habit.name}] {data.note or ''}".strip(),
            occurred_at=data.occurred_at or datetime.now(timezone.utc),
        )
        db.add(entry)
        await db.flush()
        emotion_entry_id = entry.id

    event = HabitEvent(
        user_id=user.id,
        habit_id=habit_id,
        emotion_entry_id=emotion_entry_id,
        **payload,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


@router.patch("/{habit_id}/events/{event_id}", response_model=HabitEventResponse)
async def update_event(
    habit_id: UUID,
    event_id: UUID,
    data: HabitEventUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    event = await _get_event_or_404(db, user, habit_id, event_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(event, key, value)
    await db.flush()
    await db.refresh(event)
    return event


@router.delete("/{habit_id}/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    habit_id: UUID,
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    event = await _get_event_or_404(db, user, habit_id, event_id)
    await db.delete(event)
    await db.flush()


# ─── Summary ─────────────────────────────────────────────────────────────────

@router.get("/{habit_id}/summary", response_model=HabitSummaryResponse)
async def get_summary(
    habit_id: UUID,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    habit = await _get_habit_or_404(db, user, habit_id)
    today = local_today()
    start_date_obj = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else today - timedelta(days=30)
    end_date_obj = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else today
    start, end = _date_bounds(start_date_obj, end_date_obj)

    period_result = await db.execute(
        select(HabitEvent)
        .where(HabitEvent.habit_id == habit_id, HabitEvent.user_id == user.id, HabitEvent.occurred_at >= start, HabitEvent.occurred_at <= end)
        .order_by(HabitEvent.occurred_at.asc())
    )
    period_events = period_result.scalars().all()

    all_result = await db.execute(
        select(HabitEvent)
        .where(HabitEvent.habit_id == habit_id, HabitEvent.user_id == user.id)
        .order_by(HabitEvent.occurred_at.asc())
    )
    all_events = all_result.scalars().all()

    return _build_summary(period_events, all_events, start_date_obj, end_date_obj, habit.start_date)
