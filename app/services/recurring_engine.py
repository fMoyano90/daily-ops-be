from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import calendar

from app.models.recurring_task import RecurringTask, RecurringTaskInstance, RecurringTaskType, RecurringInstanceStatus
from app.models.daily_task import DailyTask, DailyTaskStatus
from app.models.daily_plan import DailyPlan
from app.models.task import Priority


def get_tasks_for_date(recurring_tasks: list[RecurringTask], target_date: date) -> list[RecurringTask]:
    matching = []
    for rt in recurring_tasks:
        if not rt.is_active:
            continue
        if rt.recurrence_type == RecurringTaskType.daily:
            matching.append(rt)
        elif rt.recurrence_type == RecurringTaskType.weekly:
            if rt.recurrence_days and target_date.weekday() in rt.recurrence_days:
                matching.append(rt)
        elif rt.recurrence_type == RecurringTaskType.monthly:
            if rt.recurrence_days:
                last_day = calendar.monthrange(target_date.year, target_date.month)[1]
                day = min(target_date.day, last_day)
                if day in rt.recurrence_days:
                    matching.append(rt)
    return matching


async def auto_add_for_today(db: AsyncSession, plan: DailyPlan) -> int:
    today = date.today()
    today_start = datetime(today.year, today.month, today.day, 0, 0, 0)
    today_end = datetime(today.year, today.month, today.day, 23, 59, 59)

    result = await db.execute(
        select(RecurringTask)
        .where(RecurringTask.is_active == True)
        .options(selectinload(RecurringTask.project))
    )
    all_recurring = result.scalars().all()

    matching = get_tasks_for_date(all_recurring, today)

    existing_map = {}
    if matching:
        instance_result = await db.execute(
            select(RecurringTaskInstance.recurring_task_id, RecurringTaskInstance.daily_task_id)
            .where(RecurringTaskInstance.recurring_task_id.in_([rt.id for rt in matching]))
            .where(RecurringTaskInstance.date >= today_start)
            .where(RecurringTaskInstance.date <= today_end)
        )
        for row in instance_result.all():
            existing_map[row[0]] = row[1]

    added_count = 0
    for rt in matching:
        if rt.id in existing_map:
            continue

        existing_daily = await db.execute(
            select(DailyTask)
            .where(DailyTask.daily_plan_id == plan.id)
            .where(DailyTask.recurring_task_id == rt.id)
        )
        if existing_daily.scalar_one_or_none():
            continue

        daily_task_result = await db.execute(
            select(DailyTask).where(DailyTask.daily_plan_id == plan.id)
        )
        existing_tasks = daily_task_result.scalars().all()
        max_order = max([t.sort_order for t in existing_tasks], default=0)

        daily_task = DailyTask(
            daily_plan_id=plan.id,
            recurring_task_id=rt.id,
            title_snapshot=rt.title,
            priority=rt.priority,
            status=DailyTaskStatus.planned,
            sort_order=max_order + 1,
        )
        db.add(daily_task)
        await db.flush()

        instance = RecurringTaskInstance(
            recurring_task_id=rt.id,
            date=today_start,
            daily_task_id=daily_task.id,
            status=RecurringInstanceStatus.pending,
        )
        db.add(instance)
        await db.flush()

        added_count += 1

    return added_count


async def get_history_for_task(db: AsyncSession, recurring_task_id: str, limit: int = 30):
    result = await db.execute(
        select(RecurringTaskInstance)
        .where(RecurringTaskInstance.recurring_task_id == recurring_task_id)
        .order_by(RecurringTaskInstance.date.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def mark_instance_completed(db: AsyncSession, daily_task_id: str):
    result = await db.execute(
        select(RecurringTaskInstance)
        .where(RecurringTaskInstance.daily_task_id == daily_task_id)
    )
    instance = result.scalar_one_or_none()
    if instance:
        instance.status = RecurringInstanceStatus.completed
        instance.completed_at = datetime.utcnow()
        await db.flush()


async def mark_instance_skipped(db: AsyncSession, recurring_task_id: str, target_date: date):
    target_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
    target_end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)
    result = await db.execute(
        select(RecurringTaskInstance)
        .where(RecurringTaskInstance.recurring_task_id == recurring_task_id)
        .where(RecurringTaskInstance.date >= target_start)
        .where(RecurringTaskInstance.date <= target_end)
        .where(RecurringTaskInstance.status == RecurringInstanceStatus.pending)
    )
    instance = result.scalar_one_or_none()
    if instance:
        instance.status = RecurringInstanceStatus.skipped
        await db.flush()
