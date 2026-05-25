from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date
from uuid import UUID

from app.database import get_db
from app.models.daily_task import DailyTask, DailyTaskStatus
from app.models.daily_subtask import DailySubtask
from app.models.daily_plan import DailyPlan
from app.models.task import Task
from app.models.project import Project
from app.models.recurring_task import RecurringTask
from app.schemas.daily_task import DailyTaskUpdate, DailyTaskResponse
from app.services.recurring_engine import mark_instance_completed, mark_instance_skipped

router = APIRouter(prefix="/api/v1/daily-tasks", tags=["daily-tasks"])


async def get_daily_task_with_relations(db: AsyncSession, task_id: UUID):
    result = await db.execute(
        select(DailyTask)
        .where(DailyTask.id == task_id)
        .options(
            selectinload(DailyTask.subtasks),
            selectinload(DailyTask.task).selectinload(Task.project),
            selectinload(DailyTask.recurring_task).selectinload(RecurringTask.project),
        )
    )
    return result.scalar_one_or_none()


@router.patch("/{task_id}", response_model=DailyTaskResponse)
async def update_daily_task(task_id: UUID, data: DailyTaskUpdate, db: AsyncSession = Depends(get_db)):
    task = await db.get(DailyTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Daily task not found")

    update_data = data.model_dump(exclude_unset=True)
    if "status" in update_data:
        if update_data["status"] == DailyTaskStatus.completed:
            task.completed_at = datetime.utcnow()
        if update_data["status"] == DailyTaskStatus.in_progress and not task.started_at:
            task.started_at = datetime.utcnow()

    for key, value in update_data.items():
        setattr(task, key, value)

    await db.flush()
    await db.refresh(task)

    result = await get_daily_task_with_relations(db, task_id)
    return result


@router.post("/{task_id}/complete", response_model=DailyTaskResponse)
async def complete_daily_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    task = await db.get(DailyTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Daily task not found")

    task.status = DailyTaskStatus.completed
    task.completed_at = datetime.utcnow()
    await db.flush()

    if task.recurring_task_id:
        await mark_instance_completed(db, str(task_id))
        await db.flush()

    await db.refresh(task)

    result = await get_daily_task_with_relations(db, task_id)
    return result


@router.put("/{plan_id}/tasks/order")
async def reorder_tasks(plan_id: UUID, data: dict, db: AsyncSession = Depends(get_db)):
    task_ids = data.get("task_ids", [])
    result = await db.execute(
        select(DailyTask).where(DailyTask.daily_plan_id == plan_id)
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


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_daily_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    task = await db.get(DailyTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Daily task not found")

    if task.recurring_task_id:
        plan = await db.get(DailyPlan, task.daily_plan_id)
        if plan:
            await mark_instance_skipped(db, str(task.recurring_task_id), plan.date)

    await db.delete(task)
    await db.flush()
