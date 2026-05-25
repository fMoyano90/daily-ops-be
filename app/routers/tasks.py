from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime
from uuid import UUID

from app.database import get_db
from app.dependencies import get_current_user
from app.models.task import Task, TaskStatus, TaskSource, Priority
from app.models.recurring_task import RecurringTask, RecurringTaskInstance, RecurringInstanceStatus, RecurringTaskType
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse
import calendar

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    project_id: UUID | None = Query(None),
    status_filter: TaskStatus | None = Query(None, alias="status"),
    source: TaskSource | None = Query(None),
    category: str | None = Query(None),
    priority: Priority | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Task).where(Task.user_id == user.id)
    if project_id:
        query = query.where(Task.project_id == project_id)
    if status_filter:
        query = query.where(Task.status == status_filter)
    if source:
        query = query.where(Task.source == source)
    if category:
        query = query.where(Task.category == category)
    if priority:
        query = query.where(Task.priority == priority)
    query = query.order_by(Task.priority, Task.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


def recurring_matches_today(rt: RecurringTask, target_date: date) -> bool:
    if not rt.is_active:
        return False
    if rt.recurrence_type == RecurringTaskType.daily:
        return True
    elif rt.recurrence_type == RecurringTaskType.weekly:
        return rt.recurrence_days and target_date.weekday() in rt.recurrence_days
    elif rt.recurrence_type == RecurringTaskType.monthly:
        if rt.recurrence_days:
            last_day = calendar.monthrange(target_date.year, target_date.month)[1]
            day = min(target_date.day, last_day)
            return day in rt.recurrence_days
    return False


@router.get("/backlog")
async def get_backlog(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today()
    today_start = datetime(today.year, today.month, today.day, 0, 0, 0)
    today_end = datetime(today.year, today.month, today.day, 23, 59, 59)

    result = await db.execute(
        select(Task).where(Task.status == TaskStatus.backlog, Task.user_id == user.id).order_by(Task.priority, Task.created_at.desc())
    )
    backlog_tasks = result.scalars().all()

    skipped_recurring_result = await db.execute(
        select(RecurringTaskInstance)
        .join(RecurringTask)
        .where(RecurringTaskInstance.status == RecurringInstanceStatus.skipped)
        .where(RecurringTaskInstance.date >= today_start)
        .where(RecurringTaskInstance.date <= today_end)
        .where(RecurringTask.user_id == user.id)
        .options(selectinload(RecurringTaskInstance.recurring_task).selectinload(RecurringTask.project))
    )
    skipped_instances = skipped_recurring_result.scalars().all()

    recurring_tasks_map = {}
    for instance in skipped_instances:
        rt = instance.recurring_task
        if rt and recurring_matches_today(rt, today):
            if rt.id not in recurring_tasks_map:
                recurring_tasks_map[rt.id] = rt

    recurring_tasks = list(recurring_tasks_map.values())

    combined = []
    for task in backlog_tasks:
        combined.append({
            "id": str(task.id),
            "project_id": str(task.project_id),
            "title": task.title,
            "description": task.description,
            "source": task.source.value if hasattr(task.source, 'value') else task.source,
            "external_key": task.external_key,
            "external_url": task.external_url,
            "status": task.status.value if hasattr(task.status, 'value') else task.status,
            "priority": task.priority.value if hasattr(task.priority, 'value') else task.priority,
            "due_date": str(task.due_date) if task.due_date else None,
            "category": task.category,
            "created_at": str(task.created_at),
            "updated_at": str(task.updated_at),
            "is_recurring": False,
        })

    for rt in recurring_tasks:
        project = getattr(rt, 'project', None)
        combined.append({
            "id": f"recurring_{rt.id}",
            "project_id": str(rt.project_id),
            "title": rt.title,
            "description": rt.description,
            "source": "recurring",
            "external_key": None,
            "external_url": None,
            "status": "backlog",
            "priority": rt.priority.value if hasattr(rt.priority, 'value') else rt.priority,
            "due_date": None,
            "category": rt.category,
            "created_at": str(rt.created_at),
            "updated_at": str(rt.updated_at),
            "is_recurring": True,
            "recurring_task_id": str(rt.id),
        })

    combined.sort(key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x["priority"], 4))

    return combined


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(data: TaskCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = Task(**data.model_dump(), user_id=user.id)
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await db.get(Task, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: UUID, data: TaskUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await db.get(Task, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)
    await db.flush()
    await db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await db.get(Task, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.flush()
