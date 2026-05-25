from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from uuid import UUID

from app.database import get_db
from app.models.recurring_task import RecurringTask, RecurringTaskInstance, RecurringInstanceStatus
from app.models.project import Project
from app.schemas.recurring_task import (
    RecurringTaskCreate,
    RecurringTaskUpdate,
    RecurringTaskResponse,
    RecurringInstanceResponse,
)
from app.services.recurring_engine import get_history_for_task

router = APIRouter(prefix="/api/v1/recurring-tasks", tags=["recurring-tasks"])


@router.get("", response_model=list[RecurringTaskResponse])
async def list_recurring_tasks(
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    query = select(RecurringTask).options(
        selectinload(RecurringTask.project)
    )
    if active_only:
        query = query.where(RecurringTask.is_active == True)
    query = query.order_by(RecurringTask.created_at.desc())

    result = await db.execute(query)
    tasks = result.scalars().all()

    responses = []
    for task in tasks:
        stats_result = await db.execute(
            select(
                func.count(RecurringTaskInstance.id),
                func.count(RecurringTaskInstance.id).filter(
                    RecurringTaskInstance.status == RecurringInstanceStatus.completed
                )
            ).where(RecurringTaskInstance.recurring_task_id == task.id)
        )
        row = stats_result.one()
        responses.append(RecurringTaskResponse.from_orm_with_stats(
            task, instances_count=row[0], completed_count=row[1]
        ))

    return responses


@router.post("", response_model=RecurringTaskResponse, status_code=201)
async def create_recurring_task(
    data: RecurringTaskCreate,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, data.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task = RecurringTask(**data.model_dump())
    db.add(task)
    await db.flush()
    await db.refresh(task)

    result = await db.execute(
        select(RecurringTask)
        .where(RecurringTask.id == task.id)
        .options(selectinload(RecurringTask.project))
    )
    return RecurringTaskResponse.from_orm_with_stats(result.scalar_one())


@router.get("/{task_id}", response_model=RecurringTaskResponse)
async def get_recurring_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RecurringTask)
        .where(RecurringTask.id == task_id)
        .options(selectinload(RecurringTask.project))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Recurring task not found")

    stats_result = await db.execute(
        select(
            func.count(RecurringTaskInstance.id),
            func.count(RecurringTaskInstance.id).filter(
                RecurringTaskInstance.status == RecurringInstanceStatus.completed
            )
        ).where(RecurringTaskInstance.recurring_task_id == task_id)
    )
    row = stats_result.one()
    return RecurringTaskResponse.from_orm_with_stats(task, instances_count=row[0], completed_count=row[1])


@router.patch("/{task_id}", response_model=RecurringTaskResponse)
async def update_recurring_task(
    task_id: UUID,
    data: RecurringTaskUpdate,
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(RecurringTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Recurring task not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)

    await db.flush()
    await db.refresh(task)

    result = await db.execute(
        select(RecurringTask)
        .where(RecurringTask.id == task_id)
        .options(selectinload(RecurringTask.project))
    )

    stats_result = await db.execute(
        select(
            func.count(RecurringTaskInstance.id),
            func.count(RecurringTaskInstance.id).filter(
                RecurringTaskInstance.status == RecurringInstanceStatus.completed
            )
        ).where(RecurringTaskInstance.recurring_task_id == task_id)
    )
    row = stats_result.one()
    return RecurringTaskResponse.from_orm_with_stats(result.scalar_one(), instances_count=row[0], completed_count=row[1])


@router.delete("/{task_id}", status_code=204)
async def delete_recurring_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    task = await db.get(RecurringTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Recurring task not found")

    task.is_active = False
    await db.flush()


@router.get("/{task_id}/history", response_model=list[RecurringInstanceResponse])
async def get_task_history(
    task_id: UUID,
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(RecurringTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Recurring task not found")

    instances = await get_history_for_task(db, str(task_id), limit)
    return instances
