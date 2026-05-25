from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.daily_plan import DailyPlan, DailyPlanStatus
from app.models.daily_task import DailyTask, DailyTaskStatus
from app.models.task import Task, TaskStatus


async def close_day_service(db: AsyncSession, plan: DailyPlan) -> dict:
    result = await db.execute(
        select(DailyTask).where(DailyTask.daily_plan_id == plan.id)
    )
    tasks = result.scalars().all()

    completed = 0
    rolled_over = 0
    skipped = 0
    total_seconds = 0
    rolled_back_to_backlog = 0

    for task in tasks:
        total_seconds += task.total_seconds
        if task.status == DailyTaskStatus.completed:
            completed += 1
            if task.task_id:
                base_task = await db.get(Task, task.task_id)
                if base_task and base_task.status == TaskStatus.active:
                    base_task.status = TaskStatus.done
        elif task.status in [DailyTaskStatus.in_progress, DailyTaskStatus.paused, DailyTaskStatus.planned]:
            task.status = DailyTaskStatus.rolled_over
            rolled_over += 1
            if task.task_id:
                base_task = await db.get(Task, task.task_id)
                if base_task and base_task.status == TaskStatus.active:
                    base_task.status = TaskStatus.backlog
                    rolled_back_to_backlog += 1
        elif task.status == DailyTaskStatus.skipped:
            skipped += 1
            if task.task_id:
                base_task = await db.get(Task, task.task_id)
                if base_task and base_task.status == TaskStatus.active:
                    base_task.status = TaskStatus.backlog
                    rolled_back_to_backlog += 1

    plan.status = DailyPlanStatus.closed

    await db.flush()

    return {
        "completed": completed,
        "rolled_over": rolled_over,
        "skipped": skipped,
        "total_seconds": total_seconds,
        "rolled_back_to_backlog": rolled_back_to_backlog,
    }


async def auto_close_previous_days(db: AsyncSession) -> list[dict]:
    """Close all open plans from previous days (before today), per user."""
    today = date.today()

    users_result = await db.execute(select(User).where(User.is_active == True))
    users = users_result.scalars().all()

    results = []
    for user in users:
        plans_result = await db.execute(
            select(DailyPlan)
            .where(DailyPlan.user_id == user.id)
            .where(DailyPlan.date < today)
            .where(DailyPlan.status == DailyPlanStatus.open)
            .order_by(DailyPlan.date)
        )
        open_plans = plans_result.scalars().all()

        for plan in open_plans:
            summary = await close_day_service(db, plan)
            results.append({
                "plan_id": str(plan.id),
                "date": str(plan.date),
                "user_email": user.email,
                "summary": summary,
            })

    return results
