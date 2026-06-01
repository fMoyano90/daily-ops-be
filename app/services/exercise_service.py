from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_plan import DailyPlan
from app.models.exercise import ExerciseDayStatus, WorkoutDay, WorkoutExercise, WorkoutExerciseStatus
from app.models.user import User


async def get_daily_calories_burned(user_id: UUID, log_date: date, db: AsyncSession) -> int:
    """Return calories burned for completed exercises within completed (closed) workout cycles only."""
    result = await db.execute(
        select(func.coalesce(func.sum(WorkoutExercise.calories_burned), 0))
        .join(WorkoutDay, WorkoutExercise.workout_day_id == WorkoutDay.id)
        .where(
            WorkoutExercise.user_id == user_id,
            WorkoutExercise.date == log_date,
            WorkoutExercise.status == WorkoutExerciseStatus.completed,
            WorkoutDay.status == ExerciseDayStatus.completed,
        )
    )
    return int(result.scalar_one())


async def get_or_create_workout_day(db: AsyncSession, user: User, log_date: date) -> WorkoutDay:
    result = await db.execute(
        select(WorkoutDay).where(WorkoutDay.user_id == user.id, WorkoutDay.date == log_date)
    )
    day = result.scalar_one_or_none()
    if day:
        return day
    plan_result = await db.execute(
        select(DailyPlan).where(DailyPlan.user_id == user.id, DailyPlan.date == log_date)
    )
    plan = plan_result.scalar_one_or_none()
    day = WorkoutDay(user_id=user.id, daily_plan_id=plan.id if plan else None, date=log_date)
    db.add(day)
    await db.flush()
    await db.refresh(day)
    return day
