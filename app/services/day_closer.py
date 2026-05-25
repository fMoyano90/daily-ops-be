from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.daily_plan import DailyPlan, DailyPlanStatus
from app.models.daily_task import DailyTask, DailyTaskStatus


async def close_day_service(db: AsyncSession, plan: DailyPlan) -> dict:
    result = await db.execute(
        select(DailyTask).where(DailyTask.daily_plan_id == plan.id)
    )
    tasks = result.scalars().all()

    completed = 0
    rolled_over = 0
    skipped = 0
    total_seconds = 0

    for task in tasks:
        total_seconds += task.total_seconds
        if task.status == DailyTaskStatus.completed:
            completed += 1
        elif task.status in [DailyTaskStatus.in_progress, DailyTaskStatus.paused, DailyTaskStatus.planned]:
            task.status = DailyTaskStatus.rolled_over
            rolled_over += 1
        elif task.status == DailyTaskStatus.skipped:
            skipped += 1

    plan.status = DailyPlanStatus.closed

    await db.flush()

    return {
        "completed": completed,
        "rolled_over": rolled_over,
        "skipped": skipped,
        "total_seconds": total_seconds,
    }
