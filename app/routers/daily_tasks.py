from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date, timezone
from uuid import UUID

from app.database import get_db
from app.dependencies import get_current_user
from app.models.daily_task import DailyTask, DailyTaskStatus
from app.models.daily_subtask import DailySubtask
from app.models.daily_plan import DailyPlan
from app.models.task import Task, TaskStatus
from app.models.project import Project
from app.models.recurring_task import RecurringTask
from app.models.timer_session import TimerSession
from app.models.user import User
from app.schemas.daily_task import DailyTaskUpdate, DailyTaskResponse
from app.services.recurring_engine import mark_instance_completed, mark_instance_skipped
from app.services.task_status_sync import move_base_task_to_backlog_if_unused, sync_base_task_status
from app.routers.daily_plans import inject_live_seconds, inject_live_seconds_for_task

router = APIRouter(prefix="/api/v1/daily-tasks", tags=["daily-tasks"])


async def get_daily_task_with_relations(db: AsyncSession, task_id: UUID, user_id: UUID):
    result = await db.execute(
        select(DailyTask)
        .where(DailyTask.id == task_id, DailyTask.user_id == user_id)
        .options(
            selectinload(DailyTask.subtasks),
            selectinload(DailyTask.task).selectinload(Task.project),
            selectinload(DailyTask.recurring_task).selectinload(RecurringTask.project),
            selectinload(DailyTask.timer_sessions),
            selectinload(DailyTask.emotion_entries),
        )
    )
    return result.scalar_one_or_none()


async def sync_total_seconds(db: AsyncSession, task: DailyTask):
    result = await db.execute(
        select(func.sum(TimerSession.duration_seconds))
        .where(TimerSession.daily_task_id == task.id)
    )
    task.total_seconds = result.scalar() or 0


@router.patch("/{task_id}", response_model=DailyTaskResponse)
async def update_daily_task(task_id: UUID, data: DailyTaskUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await db.get(DailyTask, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Daily task not found")

    update_data = data.model_dump(exclude_unset=True)
    if "status" in update_data:
        if update_data["status"] == DailyTaskStatus.completed:
            result = await db.execute(
                select(TimerSession)
                .where(TimerSession.daily_task_id == task_id)
                .where(TimerSession.stopped_at == None)
            )
            active_session = result.scalar_one_or_none()
            if active_session:
                active_session.stopped_at = datetime.now(timezone.utc)
                delta = active_session.stopped_at - active_session.started_at
                active_session.duration_seconds = int(delta.total_seconds())
            await sync_total_seconds(db, task)
            task.completed_at = datetime.now(timezone.utc)
            await sync_base_task_status(db, task.task_id, TaskStatus.done)
        elif update_data["status"] in [DailyTaskStatus.planned, DailyTaskStatus.in_progress, DailyTaskStatus.paused]:
            await sync_base_task_status(db, task.task_id, TaskStatus.active)
        if update_data["status"] == DailyTaskStatus.in_progress and not task.started_at:
            task.started_at = datetime.now(timezone.utc)

    for key, value in update_data.items():
        setattr(task, key, value)

    await db.flush()
    await db.refresh(task)

    result = await get_daily_task_with_relations(db, task_id, user.id)
    return inject_live_seconds_for_task(result)


@router.post("/{task_id}/complete", response_model=DailyTaskResponse)
async def complete_daily_task(task_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await db.get(DailyTask, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Daily task not found")

    result = await db.execute(
        select(TimerSession)
        .where(TimerSession.daily_task_id == task_id)
        .where(TimerSession.stopped_at == None)
    )
    active_session = result.scalar_one_or_none()
    if active_session:
        active_session.stopped_at = datetime.now(timezone.utc)
        delta = active_session.stopped_at - active_session.started_at
        active_session.duration_seconds = int(delta.total_seconds())

    await sync_total_seconds(db, task)

    task.status = DailyTaskStatus.completed
    task.completed_at = datetime.now(timezone.utc)
    await sync_base_task_status(db, task.task_id, TaskStatus.done)
    await db.flush()

    if task.recurring_task_id:
        await mark_instance_completed(db, str(task_id))
        await db.flush()

    await db.refresh(task)

    result = await get_daily_task_with_relations(db, task_id, user.id)
    return inject_live_seconds_for_task(result)


@router.put("/{plan_id}/tasks/order")
async def reorder_tasks(plan_id: UUID, data: dict, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    plan = await db.get(DailyPlan, plan_id)
    if not plan or plan.user_id != user.id:
        raise HTTPException(status_code=404, detail="Plan not found")
    task_ids = data.get("task_ids", [])
    result = await db.execute(
        select(DailyTask).where(DailyTask.daily_plan_id == plan_id, DailyTask.user_id == user.id)
    )
    tasks = result.scalars().all()
    task_map = {str(t.id): t for t in tasks}

    updated_count = 0
    for i, tid in enumerate(task_ids):
        task = task_map.get(str(tid))
        if task:
            task.sort_order = i + 1
            updated_count += 1

    await db.flush()
    return {"updated_count": updated_count}


@router.post("/{task_id}/reopen", response_model=DailyTaskResponse)
async def reopen_daily_task(task_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await db.get(DailyTask, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Daily task not found")
    if task.status != DailyTaskStatus.completed:
        raise HTTPException(status_code=400, detail="Only completed tasks can be reopened")

    task.status = DailyTaskStatus.planned
    task.completed_at = None
    await sync_base_task_status(db, task.task_id, TaskStatus.active)
    await db.flush()
    await db.refresh(task)

    result = await get_daily_task_with_relations(db, task_id, user.id)
    return inject_live_seconds_for_task(result)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_daily_task(task_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await db.get(DailyTask, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Daily task not found")

    if task.recurring_task_id:
        plan = await db.get(DailyPlan, task.daily_plan_id)
        if plan:
            await mark_instance_skipped(db, str(task.recurring_task_id), plan.date)
    elif task.task_id:
        await move_base_task_to_backlog_if_unused(db, task.task_id, excluding_daily_task_id=task.id)

    await db.delete(task)
    await db.flush()
