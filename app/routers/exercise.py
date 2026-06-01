from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.exercise import ExerciseProfile, ExerciseType, WorkoutDay, WorkoutExercise
from app.models.nutrition import HealthProfile
from app.models.user import User
from app.schemas.exercise import (
    DailyContextInput,
    ExerciseProfileResponse,
    ExerciseProfileUpsert,
    WorkoutDayResponse,
    WorkoutDayUpdate,
    WorkoutExerciseCreate,
    WorkoutExerciseResponse,
    WorkoutExerciseUpdate,
    WorkoutWeekSummaryResponse,
)
from app.services import exercise_ai
from app.services.exercise_service import get_or_create_workout_day
from app.utils.timezone import local_today

router = APIRouter(prefix="/api/v1/exercise", tags=["exercise"])


async def _exercises_for_day(db: AsyncSession, workout_day_id: UUID) -> list[WorkoutExercise]:
    result = await db.execute(
        select(WorkoutExercise)
        .where(WorkoutExercise.workout_day_id == workout_day_id)
        .order_by(WorkoutExercise.sort_order.asc())
    )
    return list(result.scalars().all())


async def _day_response(db: AsyncSession, day: WorkoutDay) -> WorkoutDayResponse:
    exercises = await _exercises_for_day(db, day.id)
    return WorkoutDayResponse.model_validate({**day.__dict__, "exercises": exercises})


async def _get_exercise_or_404(db: AsyncSession, user: User, exercise_id: UUID) -> WorkoutExercise:
    result = await db.execute(
        select(WorkoutExercise).where(WorkoutExercise.id == exercise_id, WorkoutExercise.user_id == user.id)
    )
    ex = result.scalar_one_or_none()
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return ex


async def _get_day_or_404(db: AsyncSession, user: User, log_date: date) -> WorkoutDay:
    result = await db.execute(
        select(WorkoutDay).where(WorkoutDay.user_id == user.id, WorkoutDay.date == log_date)
    )
    day = result.scalar_one_or_none()
    if not day:
        raise HTTPException(status_code=404, detail="Workout day not found for this date")
    return day


# ── Profile ──────────────────────────────────────────────────────────────────

@router.get("/profile", response_model=ExerciseProfileResponse | None)
async def get_profile(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(ExerciseProfile).where(ExerciseProfile.user_id == user.id))
    return result.scalar_one_or_none()


@router.put("/profile", response_model=ExerciseProfileResponse)
async def upsert_profile(
    data: ExerciseProfileUpsert,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(ExerciseProfile).where(ExerciseProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    payload = data.model_dump()
    if profile:
        for key, value in payload.items():
            setattr(profile, key, value)
    else:
        profile = ExerciseProfile(user_id=user.id, **payload)
        db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile


# ── Daily views ───────────────────────────────────────────────────────────────

@router.get("/today", response_model=WorkoutDayResponse)
async def get_today(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    day = await get_or_create_workout_day(db, user, local_today())
    return await _day_response(db, day)


@router.get("/summary/week", response_model=WorkoutWeekSummaryResponse)
async def weekly_summary(
    week_start: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = local_today()
    start_date = week_start if week_start else today - timedelta(days=today.weekday())
    end_date = start_date + timedelta(days=6)

    result = await db.execute(
        select(WorkoutDay)
        .where(WorkoutDay.user_id == user.id, WorkoutDay.date >= start_date, WorkoutDay.date <= end_date)
        .order_by(WorkoutDay.date.asc())
    )
    days = list(result.scalars().all())

    trained = [d for d in days if d.total_duration_min and d.total_duration_min > 0]
    total_cal = sum(d.total_calories_burned or 0 for d in days)
    total_dur = sum(d.total_duration_min or 0 for d in days)
    rpe_values = [d.rpe for d in days if d.rpe is not None]
    avg_rpe = round(sum(rpe_values) / len(rpe_values), 1) if rpe_values else None

    # Streak: consecutive days from today going backwards
    streak = 0
    check = today
    all_dates = {d.date for d in trained}
    while check in all_dates:
        streak += 1
        check = check - timedelta(days=1)

    return WorkoutWeekSummaryResponse(
        period_start=start_date,
        period_end=end_date,
        total_days=len(days),
        trained_days=len(trained),
        rest_days=len(days) - len(trained),
        total_calories_burned=total_cal,
        total_duration_min=total_dur,
        avg_rpe=avg_rpe,
        streak_days=streak,
    )


@router.get("", response_model=list[WorkoutDayResponse])
async def list_days(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(WorkoutDay).where(WorkoutDay.user_id == user.id)
    if date_from:
        query = query.where(WorkoutDay.date >= date_from)
    if date_to:
        query = query.where(WorkoutDay.date <= date_to)
    result = await db.execute(query.order_by(WorkoutDay.date.desc()).limit(limit))
    days = list(result.scalars().all())
    if not days:
        return []

    day_ids = [d.id for d in days]
    ex_result = await db.execute(
        select(WorkoutExercise)
        .where(WorkoutExercise.workout_day_id.in_(day_ids))
        .order_by(WorkoutExercise.workout_day_id, WorkoutExercise.sort_order.asc())
    )
    exercises_by_day: dict[UUID, list[WorkoutExercise]] = {}
    for ex in ex_result.scalars().all():
        exercises_by_day.setdefault(ex.workout_day_id, []).append(ex)

    return [
        WorkoutDayResponse.model_validate({**day.__dict__, "exercises": exercises_by_day.get(day.id, [])})
        for day in days
    ]


@router.get("/{log_date}", response_model=WorkoutDayResponse | None)
async def get_by_date(log_date: date, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    today = local_today()
    if log_date == today:
        day = await get_or_create_workout_day(db, user, log_date)
    else:
        result = await db.execute(select(WorkoutDay).where(WorkoutDay.user_id == user.id, WorkoutDay.date == log_date))
        day = result.scalar_one_or_none()
    if not day:
        return None
    return await _day_response(db, day)


@router.delete("/{log_date}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_day(log_date: date, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    day = await _get_day_or_404(db, user, log_date)
    await db.delete(day)
    await db.flush()


@router.patch("/{log_date}", response_model=WorkoutDayResponse)
async def update_day(
    log_date: date,
    data: WorkoutDayUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    day = await _get_day_or_404(db, user, log_date)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(day, key, value)
    await db.flush()
    await db.refresh(day)
    return await _day_response(db, day)


# ── Exercise CRUD ─────────────────────────────────────────────────────────────

@router.post("/exercises", response_model=WorkoutExerciseResponse, status_code=status.HTTP_201_CREATED)
async def create_exercise(
    data: WorkoutExerciseCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    log_date = data.date or local_today()
    day = await get_or_create_workout_day(db, user, log_date)
    count_result = await db.execute(
        select(func.count(WorkoutExercise.id)).where(
            WorkoutExercise.workout_day_id == day.id
        )
    )
    count = int(count_result.scalar_one() or 0)
    payload = data.model_dump(exclude={"date"})
    ex = WorkoutExercise(
        user_id=user.id,
        workout_day_id=day.id,
        date=log_date,
        sort_order=count,
        **payload,
    )
    db.add(ex)
    await db.flush()
    await db.refresh(ex)
    return ex


@router.patch("/exercises/{exercise_id}", response_model=WorkoutExerciseResponse)
async def update_exercise(
    exercise_id: UUID,
    data: WorkoutExerciseUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ex = await _get_exercise_or_404(db, user, exercise_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(ex, key, value)
    await db.flush()
    await db.refresh(ex)
    return ex


@router.delete("/exercises/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exercise(
    exercise_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ex = await _get_exercise_or_404(db, user, exercise_id)
    await db.delete(ex)
    await db.flush()


# ── AI endpoints ──────────────────────────────────────────────────────────────

@router.post("/{log_date}/suggest", response_model=WorkoutDayResponse)
async def suggest_routine(
    log_date: date,
    context: DailyContextInput | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    day = await get_or_create_workout_day(db, user, log_date)

    profile_result = await db.execute(select(ExerciseProfile).where(ExerciseProfile.user_id == user.id))
    exercise_profile = profile_result.scalar_one_or_none()

    health_result = await db.execute(select(HealthProfile).where(HealthProfile.user_id == user.id))
    health_profile = health_result.scalar_one_or_none()

    since = log_date - timedelta(days=7)
    history_result = await db.execute(
        select(WorkoutDay)
        .where(WorkoutDay.user_id == user.id, WorkoutDay.date >= since, WorkoutDay.date < log_date)
        .order_by(WorkoutDay.date.desc())
    )
    recent_days = list(history_result.scalars().all())

    # Attach exercises to each history day for the AI context
    if recent_days:
        history_day_ids = [d.id for d in recent_days]
        hist_ex_result = await db.execute(
            select(WorkoutExercise)
            .where(WorkoutExercise.workout_day_id.in_(history_day_ids))
        )
        ex_by_day: dict[UUID, list] = {}
        for ex in hist_ex_result.scalars().all():
            ex_by_day.setdefault(ex.workout_day_id, []).append(ex)
        for d in recent_days:
            d._exercises = ex_by_day.get(d.id, [])  # type: ignore[attr-defined]

    daily_context = context.model_dump() if context else {}
    suggestions = await exercise_ai.generate_routine(exercise_profile, health_profile, recent_days, daily_context)

    # Replace all existing exercises for this day with the new routine
    await db.execute(delete(WorkoutExercise).where(WorkoutExercise.workout_day_id == day.id))

    for i, suggestion in enumerate(suggestions):
        ex = WorkoutExercise(
            user_id=user.id,
            workout_day_id=day.id,
            date=log_date,
            name=suggestion.name,
            exercise_type=ExerciseType(suggestion.exercise_type) if suggestion.exercise_type in ExerciseType._value2member_map_ else ExerciseType.cardio,
            muscle_group=suggestion.muscle_group,
            sets=suggestion.sets,
            reps=suggestion.reps,
            weight_kg=suggestion.weight_kg,
            duration_min=suggestion.duration_min,
            distance_km=suggestion.distance_km,
            intensity=suggestion.intensity,
            ai_notes=suggestion.notes,
            rest_seconds_recommended=suggestion.rest_seconds_recommended,
            ai_suggested=True,
            sort_order=i,
        )
        db.add(ex)

    await db.flush()
    await db.refresh(day)
    return await _day_response(db, day)


@router.post("/{log_date}/calculate-calories", response_model=WorkoutDayResponse)
async def calculate_calories(
    log_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    day = await _get_day_or_404(db, user, log_date)
    exercises = await _exercises_for_day(db, day.id)
    if not exercises:
        raise HTTPException(status_code=400, detail="No exercises to calculate calories for")

    health_result = await db.execute(select(HealthProfile).where(HealthProfile.user_id == user.id))
    health_profile = health_result.scalar_one_or_none()
    weight_kg = health_profile.weight_kg if health_profile else None

    calorie_result = await exercise_ai.calculate_calories(exercises, weight_kg)

    estimates_by_id = {e.exercise_id: e.calories for e in calorie_result.estimates}
    for ex in exercises:
        cal = estimates_by_id.get(str(ex.id))
        if cal is not None:
            ex.calories_burned = cal

    day.total_calories_burned = calorie_result.total_calories
    day.total_duration_min = sum(ex.duration_min or 0 for ex in exercises) or None
    day.ai_model = exercise_ai.settings.ANTHROPIC_MODEL
    day.analyzed_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(day)
    return await _day_response(db, day)


@router.post("/{log_date}/coach-message", response_model=WorkoutDayResponse)
async def coach_message(
    log_date: date,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    day = await _get_day_or_404(db, user, log_date)

    since = log_date - timedelta(days=14)
    history_result = await db.execute(
        select(WorkoutDay)
        .where(WorkoutDay.user_id == user.id, WorkoutDay.date >= since, WorkoutDay.date <= log_date)
        .order_by(WorkoutDay.date.desc())
    )
    recent_days = list(history_result.scalars().all())

    message = await exercise_ai.generate_coach_message(day, recent_days)
    day.coach_notes = message
    day.ai_model = exercise_ai.settings.ANTHROPIC_MODEL

    await db.flush()
    await db.refresh(day)
    return await _day_response(db, day)
