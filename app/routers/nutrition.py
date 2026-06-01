from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.daily_plan import DailyPlan
from app.models.nutrition import (
    ActivityLevel,
    ExerciseEntry,
    HealthProfile,
    MealEntry,
    NutritionDay,
    NutritionDayStatus,
    NutritionGoal,
    Sex,
)
from app.models.user import User
from app.schemas.nutrition import (
    ExerciseEntryCreate,
    ExerciseEntryResponse,
    ExerciseEntryUpdate,
    HealthProfileResponse,
    HealthProfileUpsert,
    MealEntryCreate,
    MealEntryResponse,
    MealEntryUpdate,
    NutritionDayResponse,
    NutritionDaySummaryResponse,
    WaterUpdate,
)
from app.services import nutrition_ai
from app.services.exercise_service import get_daily_calories_burned
from app.utils.timezone import local_today

router = APIRouter(prefix="/api/v1/nutrition", tags=["nutrition"])

ACTIVITY_FACTORS = {
    ActivityLevel.sedentary: 1.2,
    ActivityLevel.light: 1.375,
    ActivityLevel.moderate: 1.55,
    ActivityLevel.active: 1.725,
    ActivityLevel.very_active: 1.9,
}


def _avg(values: list[int | float | None]) -> float | None:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 1)


def _age(birth_date: date, today: date | None = None) -> int:
    today = today or local_today()
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return max(years, 0)


def _bmr(profile: HealthProfile) -> int:
    sex_adjustment = 5 if profile.sex == Sex.male else -161
    return round((10 * profile.weight_kg) + (6.25 * profile.height_cm) - (5 * _age(profile.birth_date)) + sex_adjustment)


def _tdee(profile: HealthProfile) -> int:
    return round(_bmr(profile) * ACTIVITY_FACTORS[profile.activity_level])


def _recommended_calories(profile: HealthProfile) -> int:
    if profile.target_calories_override is not None:
        return profile.target_calories_override
    adjustment = {NutritionGoal.lose: -500, NutritionGoal.maintain: 0, NutritionGoal.gain: 300}[profile.goal]
    return max(_tdee(profile) + adjustment, 0)


def _profile_response(profile: HealthProfile) -> HealthProfileResponse:
    return HealthProfileResponse.model_validate(
        {
            **profile.__dict__,
            "age": _age(profile.birth_date),
            "bmr": _bmr(profile),
            "tdee": _tdee(profile),
            "recommended_calories": _recommended_calories(profile),
        }
    )


async def _find_plan_for_date(db: AsyncSession, user: User, log_date: date) -> DailyPlan | None:
    result = await db.execute(select(DailyPlan).where(DailyPlan.user_id == user.id, DailyPlan.date == log_date))
    return result.scalar_one_or_none()


async def _get_or_create_day(db: AsyncSession, user: User, log_date: date) -> NutritionDay:
    result = await db.execute(select(NutritionDay).where(NutritionDay.user_id == user.id, NutritionDay.date == log_date))
    day = result.scalar_one_or_none()
    if day:
        return day
    plan = await _find_plan_for_date(db, user, log_date)
    day = NutritionDay(user_id=user.id, daily_plan_id=plan.id if plan else None, date=log_date)
    db.add(day)
    await db.flush()
    await db.refresh(day)
    return day


async def _get_day_or_404(db: AsyncSession, user: User, log_date: date) -> NutritionDay:
    result = await db.execute(select(NutritionDay).where(NutritionDay.user_id == user.id, NutritionDay.date == log_date))
    day = result.scalar_one_or_none()
    if not day:
        raise HTTPException(status_code=404, detail="Nutrition day not found for this date")
    return day


async def _entries_for_day(db: AsyncSession, user: User, log_date: date) -> tuple[list[MealEntry], list[ExerciseEntry]]:
    meals_result = await db.execute(
        select(MealEntry).where(MealEntry.user_id == user.id, MealEntry.date == log_date).order_by(MealEntry.sort_order.asc())
    )
    exercises_result = await db.execute(
        select(ExerciseEntry)
        .where(ExerciseEntry.user_id == user.id, ExerciseEntry.date == log_date)
        .order_by(ExerciseEntry.sort_order.asc())
    )
    return list(meals_result.scalars().all()), list(exercises_result.scalars().all())


async def _day_response(db: AsyncSession, user: User, day: NutritionDay) -> NutritionDayResponse:
    meals, exercises = await _entries_for_day(db, user, day.date)
    return NutritionDayResponse.model_validate({**day.__dict__, "meals": meals, "exercises": exercises})


def _day_response_with_entries(
    day: NutritionDay,
    meals_by_date: dict[date, list[MealEntry]],
    exercises_by_date: dict[date, list[ExerciseEntry]],
) -> NutritionDayResponse:
    return NutritionDayResponse.model_validate(
        {
            **day.__dict__,
            "meals": meals_by_date.get(day.date, []),
            "exercises": exercises_by_date.get(day.date, []),
        }
    )


def _validate_analysis_indexes(analysis, meal_count: int, exercise_count: int) -> None:
    meal_indexes = [item.index for item in analysis.meals]
    exercise_indexes = [item.index for item in analysis.exercises]
    expected_meals = set(range(meal_count))
    expected_exercises = set(range(exercise_count))
    if len(meal_indexes) != len(set(meal_indexes)) or set(meal_indexes) != expected_meals:
        raise HTTPException(status_code=502, detail="Claude returned mismatched meal indexes")
    if len(exercise_indexes) != len(set(exercise_indexes)) or set(exercise_indexes) != expected_exercises:
        raise HTTPException(status_code=502, detail="Claude returned mismatched exercise indexes")


async def _get_meal_or_404(db: AsyncSession, user: User, meal_id: UUID) -> MealEntry:
    result = await db.execute(select(MealEntry).where(MealEntry.id == meal_id, MealEntry.user_id == user.id))
    meal = result.scalar_one_or_none()
    if not meal:
        raise HTTPException(status_code=404, detail="Meal entry not found")
    return meal


async def _get_exercise_or_404(db: AsyncSession, user: User, exercise_id: UUID) -> ExerciseEntry:
    result = await db.execute(select(ExerciseEntry).where(ExerciseEntry.id == exercise_id, ExerciseEntry.user_id == user.id))
    exercise = result.scalar_one_or_none()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise entry not found")
    return exercise


def _reset_day_analysis(day: NutritionDay) -> None:
    day.status = NutritionDayStatus.draft
    day.analyzed_at = None
    day.ai_model = None
    day.ai_summary = None
    day.recommended_calories = None
    day.consumed_calories = None
    day.burned_calories = None
    day.balance_calories = None
    day.total_protein_g = None
    day.total_carbs_g = None
    day.total_sugar_g = None
    day.total_fat_g = None
    day.total_fiber_g = None


@router.get("/profile", response_model=HealthProfileResponse | None)
async def get_profile(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(HealthProfile).where(HealthProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    return _profile_response(profile) if profile else None


@router.put("/profile", response_model=HealthProfileResponse)
async def upsert_profile(
    data: HealthProfileUpsert,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(HealthProfile).where(HealthProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    payload = data.model_dump()
    if profile:
        for key, value in payload.items():
            setattr(profile, key, value)
    else:
        profile = HealthProfile(user_id=user.id, **payload)
        db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return _profile_response(profile)


@router.get("/today", response_model=NutritionDayResponse)
async def get_today(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    day = await _get_or_create_day(db, user, local_today())
    return await _day_response(db, user, day)


@router.get("", response_model=list[NutritionDayResponse])
async def list_days(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(NutritionDay).where(NutritionDay.user_id == user.id)
    if date_from:
        query = query.where(NutritionDay.date >= date_from)
    if date_to:
        query = query.where(NutritionDay.date <= date_to)
    result = await db.execute(query.order_by(NutritionDay.date.desc()).limit(limit))
    days = result.scalars().all()
    if not days:
        return []

    dates = [day.date for day in days]
    meals_result = await db.execute(
        select(MealEntry)
        .where(MealEntry.user_id == user.id, MealEntry.date.in_(dates))
        .order_by(MealEntry.date.desc(), MealEntry.sort_order.asc())
    )
    exercises_result = await db.execute(
        select(ExerciseEntry)
        .where(ExerciseEntry.user_id == user.id, ExerciseEntry.date.in_(dates))
        .order_by(ExerciseEntry.date.desc(), ExerciseEntry.sort_order.asc())
    )

    meals_by_date: dict[date, list[MealEntry]] = {}
    for meal in meals_result.scalars().all():
        meals_by_date.setdefault(meal.date, []).append(meal)

    exercises_by_date: dict[date, list[ExerciseEntry]] = {}
    for exercise in exercises_result.scalars().all():
        exercises_by_date.setdefault(exercise.date, []).append(exercise)

    return [_day_response_with_entries(day, meals_by_date, exercises_by_date) for day in days]


@router.get("/summary/week", response_model=NutritionDaySummaryResponse)
async def weekly_summary(
    week_start: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = local_today()
    start_date = week_start if week_start else today - timedelta(days=today.weekday())
    end_date = start_date + timedelta(days=6)
    result = await db.execute(
        select(NutritionDay)
        .where(NutritionDay.user_id == user.id, NutritionDay.date >= start_date, NutritionDay.date <= end_date)
        .order_by(NutritionDay.date.asc())
    )
    days = result.scalars().all()
    return NutritionDaySummaryResponse(
        period_start=start_date,
        period_end=end_date,
        total_days=len(days),
        analyzed_days=len([day for day in days if day.status == NutritionDayStatus.analyzed]),
        avg_recommended_calories=_avg([day.recommended_calories for day in days]),
        avg_consumed_calories=_avg([day.consumed_calories for day in days]),
        avg_burned_calories=_avg([day.burned_calories for day in days]),
        avg_balance_calories=_avg([day.balance_calories for day in days]),
        total_water_ml=sum(day.water_ml or 0 for day in days),
        avg_protein_g=_avg([day.total_protein_g for day in days]),
        avg_carbs_g=_avg([day.total_carbs_g for day in days]),
        avg_sugar_g=_avg([day.total_sugar_g for day in days]),
        avg_fat_g=_avg([day.total_fat_g for day in days]),
    )


@router.get("/{log_date}", response_model=NutritionDayResponse)
async def get_by_date(log_date: date, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    day = await _get_or_create_day(db, user, log_date)
    return await _day_response(db, user, day)


@router.post("/meals", response_model=MealEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_meal(
    data: MealEntryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    log_date = data.date or local_today()
    day = await _get_or_create_day(db, user, log_date)
    count_result = await db.execute(select(func.count(MealEntry.id)).where(MealEntry.user_id == user.id, MealEntry.date == log_date))
    count = int(count_result.scalar_one() or 0)
    meal = MealEntry(
        user_id=user.id,
        daily_plan_id=day.daily_plan_id,
        date=log_date,
        label=data.label or f"Comida {count + 1}",
        description=data.description.strip(),
        sort_order=count,
    )
    _reset_day_analysis(day)
    db.add(meal)
    await db.flush()
    await db.refresh(meal)
    return meal


@router.patch("/meals/{meal_id}", response_model=MealEntryResponse)
async def update_meal(
    meal_id: UUID,
    data: MealEntryUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    meal = await _get_meal_or_404(db, user, meal_id)
    day = await _get_or_create_day(db, user, meal.date)
    payload = data.model_dump(exclude_unset=True)
    description_changed = "description" in payload and payload["description"] != meal.description
    for key, value in payload.items():
        setattr(meal, key, value.strip() if isinstance(value, str) else value)
    if description_changed:
        meal.calories = None
        meal.protein_g = None
        meal.carbs_g = None
        meal.sugar_g = None
        meal.fat_g = None
        meal.fiber_g = None
        meal.ai_notes = None
        _reset_day_analysis(day)
    await db.flush()
    await db.refresh(meal)
    return meal


@router.delete("/meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal(meal_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    meal = await _get_meal_or_404(db, user, meal_id)
    day = await _get_or_create_day(db, user, meal.date)
    _reset_day_analysis(day)
    await db.delete(meal)
    await db.flush()


@router.post("/exercises", response_model=ExerciseEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_exercise(
    data: ExerciseEntryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    log_date = data.date or local_today()
    day = await _get_or_create_day(db, user, log_date)
    count_result = await db.execute(
        select(func.count(ExerciseEntry.id)).where(ExerciseEntry.user_id == user.id, ExerciseEntry.date == log_date)
    )
    count = int(count_result.scalar_one() or 0)
    exercise = ExerciseEntry(
        user_id=user.id,
        daily_plan_id=day.daily_plan_id,
        date=log_date,
        label=data.label or f"Ejercicio {count + 1}",
        description=data.description.strip(),
        sort_order=count,
    )
    _reset_day_analysis(day)
    db.add(exercise)
    await db.flush()
    await db.refresh(exercise)
    return exercise


@router.patch("/exercises/{exercise_id}", response_model=ExerciseEntryResponse)
async def update_exercise(
    exercise_id: UUID,
    data: ExerciseEntryUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    exercise = await _get_exercise_or_404(db, user, exercise_id)
    day = await _get_or_create_day(db, user, exercise.date)
    payload = data.model_dump(exclude_unset=True)
    description_changed = "description" in payload and payload["description"] != exercise.description
    for key, value in payload.items():
        setattr(exercise, key, value.strip() if isinstance(value, str) else value)
    if description_changed:
        exercise.calories_burned = None
        exercise.duration_min = None
        exercise.intensity = None
        exercise.ai_notes = None
        _reset_day_analysis(day)
    await db.flush()
    await db.refresh(exercise)
    return exercise


@router.delete("/exercises/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exercise(exercise_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    exercise = await _get_exercise_or_404(db, user, exercise_id)
    day = await _get_or_create_day(db, user, exercise.date)
    _reset_day_analysis(day)
    await db.delete(exercise)
    await db.flush()


@router.post("/{log_date}/water", response_model=NutritionDayResponse)
async def update_water(
    log_date: date,
    data: WaterUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    day = await _get_or_create_day(db, user, log_date)
    profile_result = await db.execute(select(HealthProfile).where(HealthProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    glass_ml = profile.glass_ml if profile else 200
    if data.water_ml is not None:
        day.water_ml = data.water_ml
    else:
        day.water_ml = max((day.water_ml or 0) + ((data.delta or 0) * glass_ml), 0)
    await db.flush()
    await db.refresh(day)
    return await _day_response(db, user, day)


@router.post("/{log_date}/analyze", response_model=NutritionDayResponse)
async def analyze_day(log_date: date, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    profile_result = await db.execute(select(HealthProfile).where(HealthProfile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=400, detail="Health profile is required before analyzing nutrition")

    meals, _ = await _entries_for_day(db, user, log_date)
    analysis = await nutrition_ai.analyze_day(profile, meals, [])
    _validate_analysis_indexes(analysis, len(meals), 0)

    day = await _get_or_create_day(db, user, log_date)

    meal_by_index = {item.index: item for item in analysis.meals}
    for idx, meal in enumerate(meals):
        item = meal_by_index.get(idx)
        if not item:
            continue
        meal.calories = item.calories
        meal.protein_g = item.protein_g
        meal.carbs_g = item.carbs_g
        meal.sugar_g = item.sugar_g
        meal.fat_g = item.fat_g
        meal.fiber_g = item.fiber_g
        meal.ai_notes = item.notes

    consumed = sum(meal.calories or 0 for meal in meals)
    burned = await get_daily_calories_burned(user.id, log_date, db)
    tdee = _tdee(profile)
    day.recommended_calories = _recommended_calories(profile)
    day.consumed_calories = consumed
    day.burned_calories = burned
    day.balance_calories = consumed - (tdee + burned)
    day.total_protein_g = round(sum(meal.protein_g or 0 for meal in meals), 1)
    day.total_carbs_g = round(sum(meal.carbs_g or 0 for meal in meals), 1)
    day.total_sugar_g = round(sum(meal.sugar_g or 0 for meal in meals), 1)
    day.total_fat_g = round(sum(meal.fat_g or 0 for meal in meals), 1)
    day.total_fiber_g = round(sum(meal.fiber_g or 0 for meal in meals), 1)
    day.ai_summary = analysis.day_summary
    day.ai_model = nutrition_ai.settings.ANTHROPIC_MODEL
    day.analyzed_at = datetime.now(timezone.utc)
    day.status = NutritionDayStatus.analyzed

    await db.flush()
    await db.refresh(day)
    return await _day_response(db, user, day)
