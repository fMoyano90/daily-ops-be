from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, timedelta
from uuid import UUID

from app.database import get_db
from app.dependencies import get_current_user
from app.models.daily_plan import DailyPlan, DailyPlanStatus
from app.models.daily_task import DailyTask, DailyTaskStatus
from app.models.daily_subtask import DailySubtask
from app.models.task import Task
from app.models.project import Project
from app.models.user import User
from app.utils.timezone import local_today

router = APIRouter(prefix="/api/v1/history", tags=["history"])


def serialize_task(t):
    project = getattr(t, 'task', None)
    project_data = None
    if project and hasattr(project, 'project'):
        p = project.project
        project_data = {
            "id": str(p.id),
            "name": p.name,
            "type": p.type.value if hasattr(p.type, 'value') else p.type,
            "color": p.color,
            "is_active": p.is_active,
            "created_at": str(p.created_at),
        }
    return {
        "id": str(t.id),
        "daily_plan_id": str(t.daily_plan_id),
        "task_id": str(t.task_id) if t.task_id else None,
        "title_snapshot": t.title_snapshot,
        "priority": t.priority.value if hasattr(t.priority, 'value') else t.priority,
        "status": t.status.value if hasattr(t.status, 'value') else t.status,
        "estimated_seconds": t.estimated_seconds,
        "total_seconds": t.total_seconds,
        "sort_order": t.sort_order,
        "started_at": str(t.started_at) if t.started_at else None,
        "completed_at": str(t.completed_at) if t.completed_at else None,
        "subtasks": [
            {
                "id": str(s.id),
                "daily_task_id": str(s.daily_task_id),
                "title": s.title,
                "status": s.status.value if hasattr(s.status, 'value') else s.status,
                "priority": s.priority.value if hasattr(s.priority, 'value') else s.priority,
                "sort_order": s.sort_order,
            }
            for s in getattr(t, 'subtasks', [])
        ],
        "project": project_data,
    }


@router.get("")
async def list_history(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(DailyPlan).where(DailyPlan.status == DailyPlanStatus.closed, DailyPlan.user_id == user.id)
    if from_date:
        query = query.where(DailyPlan.date >= from_date)
    if to_date:
        query = query.where(DailyPlan.date <= to_date)
    query = query.order_by(DailyPlan.date.desc()).limit(limit)

    result = await db.execute(query)
    plans = result.scalars().all()

    history = []
    for plan in plans:
        tasks_result = await db.execute(
            select(DailyTask)
            .where(DailyTask.daily_plan_id == plan.id)
            .options(
                selectinload(DailyTask.subtasks),
                selectinload(DailyTask.task).selectinload(Task.project),
            )
            .order_by(DailyTask.sort_order)
        )
        tasks = tasks_result.scalars().all()

        completed = sum(1 for t in tasks if t.status == DailyTaskStatus.completed)
        rolled = sum(1 for t in tasks if t.status == DailyTaskStatus.rolled_over)
        total_secs = sum(t.total_seconds for t in tasks)

        history.append({
            "plan_id": str(plan.id),
            "date": plan.date.isoformat(),
            "status": plan.status.value if hasattr(plan.status, 'value') else plan.status,
            "total_tasks": len(tasks),
            "completed_tasks": completed,
            "rolled_over_tasks": rolled,
            "total_seconds": total_secs,
            "tasks": [serialize_task(t) for t in tasks],
        })

    return history


@router.get("/{history_date}")
async def get_history_by_date(history_date: date, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(DailyPlan).where(DailyPlan.date == history_date, DailyPlan.user_id == user.id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="No plan found for this date")

    tasks_result = await db.execute(
        select(DailyTask)
        .where(DailyTask.daily_plan_id == plan.id)
        .options(
            selectinload(DailyTask.subtasks),
            selectinload(DailyTask.task).selectinload(Task.project),
        )
        .order_by(DailyTask.sort_order)
    )
    tasks = tasks_result.scalars().all()

    completed = sum(1 for t in tasks if t.status == DailyTaskStatus.completed)
    rolled = sum(1 for t in tasks if t.status == DailyTaskStatus.rolled_over)
    total_secs = sum(t.total_seconds for t in tasks)

    return {
        "plan_id": str(plan.id),
        "date": plan.date.isoformat(),
        "status": plan.status.value if hasattr(plan.status, 'value') else plan.status,
        "total_tasks": len(tasks),
        "completed_tasks": completed,
        "rolled_over_tasks": rolled,
        "total_seconds": total_secs,
        "tasks": [serialize_task(t) for t in tasks],
    }


@router.get("/summary/week")
async def get_weekly_summary(
    week_start: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not week_start:
        today = local_today()
        week_start = today - timedelta(days=today.weekday())

    week_end = week_start + timedelta(days=6)

    plans_result = await db.execute(
        select(DailyPlan)
        .where(DailyPlan.date >= week_start, DailyPlan.user_id == user.id)
        .where(DailyPlan.date <= week_end)
        .where(DailyPlan.status == DailyPlanStatus.closed)
    )
    plans = plans_result.scalars().all()

    total_completed = 0
    total_rolled_over = 0
    total_seconds = 0
    by_project = {}
    by_day = []

    for plan in plans:
        tasks_result = await db.execute(
            select(DailyTask).where(DailyTask.daily_plan_id == plan.id)
        )
        tasks = tasks_result.scalars().all()

        day_completed = 0
        day_seconds = 0

        for task in tasks:
            if task.status == DailyTaskStatus.completed:
                day_completed += 1
                day_seconds += task.total_seconds

        total_completed += day_completed
        total_seconds += day_seconds
        rolled = sum(1 for t in tasks if t.status == DailyTaskStatus.rolled_over)
        total_rolled_over += rolled

        by_day.append({
            "date": plan.date.isoformat(),
            "completed": day_completed,
            "seconds": day_seconds,
        })

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "total_completed": total_completed,
        "total_rolled_over": total_rolled_over,
        "total_seconds": total_seconds,
        "by_project": [],
        "by_day": by_day,
    }
