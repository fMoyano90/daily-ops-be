"""Task reminder scheduler service.

Scans for pending task reminders and sends push notifications via Web Push.
Runs every minute from the APScheduler.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session
from app.models.daily_task import DailyTask, DailyTaskStatus
from app.models.daily_plan import DailyPlan
from app.models.recurring_task import (
    RecurringTask,
    RecurringTaskInstance,
    RecurringInstanceStatus,
    RecurringTaskType,
)
from app.models.task import Task, TaskStatus
from app.models.task_reminder import TaskReminderDelivery
from app.services.push import send_to_user
from app.utils.timezone import app_tz, local_now, local_today

logger = logging.getLogger(__name__)

REMINDER_OPTIONS = [0, 15, 30, 60, 180]

WINDOW_MINUTES = 2


def _compute_reminder_datetime(
    *,
    base_date: date | datetime,
    meeting_time,
    minutes_before: int,
) -> datetime | None:
    """Combine date + meeting_time, subtract offset, return aware datetime."""
    if meeting_time is None:
        return None
    hour = meeting_time.hour if hasattr(meeting_time, "hour") else int(str(meeting_time).split(":")[0])
    minute = meeting_time.minute if hasattr(meeting_time, "minute") else int(str(meeting_time).split(":")[1])
    second = getattr(meeting_time, "second", 0)
    local_date = base_date.date() if isinstance(base_date, datetime) else base_date
    naive = datetime.combine(local_date, time(hour=hour, minute=minute, second=second))
    local_dt = naive.replace(tzinfo=app_tz())
    return local_dt - timedelta(minutes=minutes_before)


def _recurring_matches_date(rt, target_date) -> bool:
    import calendar
    if not rt.is_active:
        return False
    if rt.recurrence_type == RecurringTaskType.daily:
        return True
    if rt.recurrence_type == RecurringTaskType.weekly:
        return rt.recurrence_days and target_date.weekday() in rt.recurrence_days
    if rt.recurrence_type == RecurringTaskType.monthly:
        if rt.recurrence_days:
            last_day = calendar.monthrange(target_date.year, target_date.month)[1]
            day = min(target_date.day, last_day)
            return day in rt.recurrence_days
    return False


async def process_reminders() -> int:
    """Scan for due reminders and send push notifications.

    Returns the number of reminders sent.
    """
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
        return 0

    now = local_now()
    window_start = now - timedelta(minutes=WINDOW_MINUTES)

    async with async_session() as db:
        await _send_manual_task_reminders(db, now, window_start)
        await db.commit()

        await _send_recurring_task_reminders(db, now, window_start)
        await db.commit()

    return 0


async def _send_manual_task_reminders(
    db: AsyncSession,
    now: datetime,
    window_start: datetime,
) -> int:
    """Send reminders for manual tasks.

    Two sources:
    1. Tasks with due_date + meeting_time + reminder set (backlog / future)
    2. Tasks in today's daily plan with meeting_time + reminder set (today view)
    """
    today = local_today()
    sent = 0

    # Source 1: Tasks with due_date set
    result = await db.execute(
        select(Task).where(
            Task.reminder_minutes_before.isnot(None),
            Task.reminder_minutes_before >= 0,
            Task.meeting_time.isnot(None),
            Task.due_date.isnot(None),
            Task.status.in_([TaskStatus.backlog, TaskStatus.active]),
        )
    )
    tasks_with_due = result.scalars().all()

    for task in tasks_with_due:
        minutes = task.reminder_minutes_before
        reminder_dt = _compute_reminder_datetime(
            base_date=task.due_date,
            meeting_time=task.meeting_time,
            minutes_before=minutes,
        )
        if reminder_dt is None:
            continue
        if not (window_start <= reminder_dt <= now):
            continue
        if await _already_sent(db, task_id=task.id, reminder_dt=reminder_dt, minutes=minutes):
            continue

        await send_to_user(
            db, task.user_id,
            title=f"⏰ {task.title}",
            body=f"Comienza en {_format_minutes(minutes)}",
            url="/today",
        )
        db.add(TaskReminderDelivery(
            user_id=task.user_id,
            task_id=task.id,
            reminder_date=reminder_dt,
            minutes_before=minutes,
        ))
        sent += 1

    # Source 2: Tasks in today's plans with meeting_time + reminder (no due_date needed)
    daily_tasks_result = await db.execute(
        select(DailyTask)
        .join(DailyPlan, DailyPlan.id == DailyTask.daily_plan_id)
        .where(
            DailyPlan.date == today,
            DailyTask.task_id.isnot(None),
            DailyTask.status.in_([DailyTaskStatus.planned, DailyTaskStatus.in_progress, DailyTaskStatus.paused]),
        )
        .options(selectinload(DailyTask.task))
    )
    daily_tasks = daily_tasks_result.scalars().all()

    for dt in daily_tasks:
        source_task = dt.task
        if source_task is None:
            continue
        if source_task.reminder_minutes_before is None:
            continue
        if source_task.meeting_time is None:
            continue

        minutes = source_task.reminder_minutes_before
        reminder_dt = _compute_reminder_datetime(
            base_date=today,
            meeting_time=source_task.meeting_time,
            minutes_before=minutes,
        )
        if reminder_dt is None:
            continue
        if not (window_start <= reminder_dt <= now):
            continue
        if await _already_sent(db, task_id=source_task.id, reminder_dt=reminder_dt, minutes=minutes):
            continue

        await send_to_user(
            db, source_task.user_id,
            title=f"⏰ {source_task.title}",
            body=f"Comienza en {_format_minutes(minutes)}",
            url="/today",
        )
        db.add(TaskReminderDelivery(
            user_id=source_task.user_id,
            task_id=source_task.id,
            reminder_date=reminder_dt,
            minutes_before=minutes,
        ))
        sent += 1

    return sent


async def _send_recurring_task_reminders(
    db: AsyncSession,
    now: datetime,
    window_start: datetime,
) -> int:
    """Send reminders for recurring tasks that occur today."""
    result = await db.execute(
        select(RecurringTask).where(
            RecurringTask.reminder_minutes_before.isnot(None),
            RecurringTask.reminder_minutes_before >= 0,
            RecurringTask.is_active == True,
            RecurringTask.meeting_time.isnot(None),
        ).options(selectinload(RecurringTask.instances))
    )
    recurring_tasks = result.scalars().all()
    today = local_today()
    sent = 0

    for rt in recurring_tasks:
        if not _recurring_matches_date(rt, today):
            continue

        minutes = rt.reminder_minutes_before

        instance = None
        for inst in rt.instances:
            if inst.date.date() == today and inst.status == RecurringInstanceStatus.pending:
                instance = inst
                break

        if instance is None:
            continue

        reminder_dt = _compute_reminder_datetime(
            base_date=today,
            meeting_time=rt.meeting_time,
            minutes_before=minutes,
        )
        if reminder_dt is None:
            continue
        if not (window_start <= reminder_dt <= now):
            continue
        if await _already_sent(db, recurring_task_id=rt.id, reminder_dt=reminder_dt, minutes=minutes):
            continue

        await send_to_user(
            db, rt.user_id,
            title=f"⏰ {rt.title}",
            body=f"Comienza en {_format_minutes(minutes)}",
            url="/today",
        )
        db.add(TaskReminderDelivery(
            user_id=rt.user_id,
            recurring_task_id=rt.id,
            reminder_date=reminder_dt,
            minutes_before=minutes,
        ))
        sent += 1

    return sent


async def _already_sent(
    db: AsyncSession,
    *,
    task_id: UUID = None,
    recurring_task_id: UUID = None,
    reminder_dt: datetime,
    minutes: int,
) -> bool:
    """Check if this reminder was already sent."""
    conditions = [
        TaskReminderDelivery.reminder_date == reminder_dt,
        TaskReminderDelivery.minutes_before == minutes,
    ]
    if task_id is not None:
        conditions.append(TaskReminderDelivery.task_id == task_id)
    if recurring_task_id is not None:
        conditions.append(TaskReminderDelivery.recurring_task_id == recurring_task_id)

    result = await db.execute(
        select(TaskReminderDelivery).where(and_(*conditions))
    )
    return result.scalar_one_or_none() is not None


def _format_minutes(minutes: int) -> str:
    if minutes == 0:
        return "ahora"
    if minutes == 15:
        return "15 min"
    if minutes == 30:
        return "30 min"
    if minutes == 60:
        return "1h"
    if minutes == 180:
        return "3h"
    return f"{minutes} min"
