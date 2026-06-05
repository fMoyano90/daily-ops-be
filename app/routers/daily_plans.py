from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from app.database import get_db
from app.dependencies import get_current_user
from app.models.daily_plan import DailyPlan, DailyPlanStatus
from app.models.daily_task import DailyTask, DailyTaskStatus
from app.models.task import Task, TaskStatus
from app.models.project import Project
from app.models.daily_reflection import DailyReflection
from app.models.recurring_task import RecurringTask, RecurringTaskInstance, RecurringInstanceStatus
from app.models.user import User
from app.schemas.daily_plan import DailyPlanCreate, DailyPlanUpdate, DailyPlanResponse, DailyPlanCloseRequest
from app.schemas.daily_task import DailyTaskResponse
from app.schemas.project import ProjectResponse
from app.schemas.task import TaskResponse
from app.services.day_closer import close_day_service
from app.services.recurring_engine import auto_add_for_today
from app.services.subtask_carryover import carry_over_subtasks
from app.services.task_status_sync import sync_base_task_status
from app.utils.timezone import local_today

router = APIRouter(prefix="/api/v1/daily-plans", tags=["daily-plans"])


def _has_reflection_content(reflection_payload: dict) -> bool:
    for value in reflection_payload.values():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return True
    return False


async def _save_optional_reflection(db: AsyncSession, plan: DailyPlan, reflection_payload: dict):
    result = await db.execute(
        select(DailyReflection).where(DailyReflection.user_id == plan.user_id, DailyReflection.daily_plan_id == plan.id)
    )
    reflection = result.scalar_one_or_none()
    if reflection:
        for key, value in reflection_payload.items():
            setattr(reflection, key, value)
        return reflection

    reflection = DailyReflection(user_id=plan.user_id, daily_plan_id=plan.id, **reflection_payload)
    db.add(reflection)
    await db.flush()
    return reflection


def compute_live_total_seconds(task: DailyTask) -> int:
    live = task.total_seconds
    now = datetime.now(timezone.utc)
    for session in task.timer_sessions:
        if session.stopped_at is None:
            started = session.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            delta = int((now - started).total_seconds())
            live += max(0, delta)
    return live


def inject_live_seconds_for_task(task: DailyTask):
    task.live_total_seconds = compute_live_total_seconds(task)
    return task


def inject_live_seconds(plan: DailyPlan):
    for task in plan.tasks:
        task.live_total_seconds = compute_live_total_seconds(task)
    return plan


def _today_plan_query(user_id: UUID):
    """Reusable query builder with all eager loads for daily plans."""
    return (
        select(DailyPlan)
        .where(DailyPlan.user_id == user_id)
        .options(
            selectinload(DailyPlan.tasks).selectinload(DailyTask.subtasks),
            selectinload(DailyPlan.tasks).selectinload(DailyTask.task).selectinload(Task.project),
            selectinload(DailyPlan.tasks).selectinload(DailyTask.task).selectinload(Task.description_attachments),
            selectinload(DailyPlan.tasks).selectinload(DailyTask.recurring_task).selectinload(RecurringTask.project),
            selectinload(DailyPlan.tasks).selectinload(DailyTask.recurring_task).selectinload(RecurringTask.description_attachments),
            selectinload(DailyPlan.tasks).selectinload(DailyTask.timer_sessions),
            selectinload(DailyPlan.tasks).selectinload(DailyTask.emotion_entries),
        )
    )


@router.get("/today", response_model=DailyPlanResponse)
async def get_today_plan(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    today = local_today()

    result = await db.execute(_today_plan_query(user.id).where(DailyPlan.date == today))
    plan = result.scalar_one_or_none()

    if not plan:
        plan = DailyPlan(date=today, user_id=user.id)
        db.add(plan)
        await db.commit()

        await auto_add_for_today(db, plan)
        await db.commit()

        result = await db.execute(_today_plan_query(user.id).where(DailyPlan.id == plan.id))
        plan = result.scalar_one()
    else:
        await auto_add_for_today(db, plan)
        await db.commit()

        result = await db.execute(_today_plan_query(user.id).where(DailyPlan.id == plan.id))
        plan = result.scalar_one()

    return inject_live_seconds(plan)


@router.get("/{plan_date}", response_model=DailyPlanResponse)
async def get_plan_by_date(plan_date: date, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(DailyPlan)
        .where(DailyPlan.date == plan_date, DailyPlan.user_id == user.id)
        .options(
            selectinload(DailyPlan.tasks).selectinload(DailyTask.subtasks),
            selectinload(DailyPlan.tasks).selectinload(DailyTask.task).selectinload(Task.project),
            selectinload(DailyPlan.tasks).selectinload(DailyTask.task).selectinload(Task.description_attachments),
            selectinload(DailyPlan.tasks).selectinload(DailyTask.recurring_task).selectinload(RecurringTask.project),
            selectinload(DailyPlan.tasks).selectinload(DailyTask.recurring_task).selectinload(RecurringTask.description_attachments),
            selectinload(DailyPlan.tasks).selectinload(DailyTask.timer_sessions),
            selectinload(DailyPlan.tasks).selectinload(DailyTask.emotion_entries),
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found for this date")
    return plan


@router.post("", response_model=DailyPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_daily_plan(data: DailyPlanCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(DailyPlan).where(DailyPlan.date == data.date, DailyPlan.user_id == user.id))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Plan already exists for this date")
    plan = DailyPlan(**data.model_dump(), user_id=user.id)
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return plan


@router.post("/today/tasks", response_model=DailyPlanResponse, status_code=status.HTTP_201_CREATED)
async def select_tasks_for_today(task_ids: list[UUID], db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    today = local_today()
    result = await db.execute(select(DailyPlan).where(DailyPlan.date == today, DailyPlan.user_id == user.id))
    plan = result.scalar_one_or_none()
    if not plan:
        plan = DailyPlan(date=today, user_id=user.id)
        db.add(plan)
        await db.flush()
        await db.refresh(plan)

    existing_result = await db.execute(select(DailyTask).where(DailyTask.daily_plan_id == plan.id))
    existing_tasks = existing_result.scalars().all()
    max_order = max([t.sort_order for t in existing_tasks], default=0)

    added = []
    for i, task_id in enumerate(task_ids):
        task = await db.get(Task, task_id)
        if not task or task.user_id != user.id:
            continue
        daily_task = DailyTask(
            user_id=plan.user_id,
            daily_plan_id=plan.id,
            task_id=task.id,
            title_snapshot=task.title,
            priority=task.priority,
            estimated_seconds=task.estimated_seconds,
            status=DailyTaskStatus.planned,
            sort_order=max_order + i + 1,
        )
        db.add(daily_task)
        await sync_base_task_status(db, task.id, TaskStatus.active)
        added.append(daily_task)

    await db.flush()
    for dt in added:
        await carry_over_subtasks(db, dt)
    await db.flush()
    for dt in added:
        await db.refresh(dt)

    result = await db.execute(
        select(DailyPlan)
        .where(DailyPlan.id == plan.id)
        .options(
            selectinload(DailyPlan.tasks)
            .selectinload(DailyTask.subtasks),
            selectinload(DailyPlan.tasks)
            .selectinload(DailyTask.task)
            .selectinload(Task.project),
            selectinload(DailyPlan.tasks)
            .selectinload(DailyTask.task)
            .selectinload(Task.description_attachments),
            selectinload(DailyPlan.tasks)
            .selectinload(DailyTask.recurring_task).selectinload(RecurringTask.project),
            selectinload(DailyPlan.tasks)
            .selectinload(DailyTask.recurring_task).selectinload(RecurringTask.description_attachments),
            selectinload(DailyPlan.tasks)
            .selectinload(DailyTask.timer_sessions),
            selectinload(DailyPlan.tasks)
            .selectinload(DailyTask.emotion_entries),
        )
    )
    return inject_live_seconds(result.scalar_one())


@router.post("/{plan_id}/tasks", response_model=DailyTaskResponse, status_code=status.HTTP_201_CREATED)
async def add_task_to_plan(plan_id: UUID, data: dict, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    plan = await db.get(DailyPlan, plan_id)
    if not plan or plan.user_id != user.id:
        raise HTTPException(status_code=404, detail="Plan not found")

    task_id = data.get("task_id")
    recurring_task_id = data.get("recurring_task_id")
    priority = data.get("priority", "medium")

    result = await db.execute(select(DailyTask).where(DailyTask.daily_plan_id == plan_id, DailyTask.user_id == user.id))
    existing = result.scalars().all()
    max_order = max([t.sort_order for t in existing], default=0)

    if task_id and task_id.startswith("recurring_"):
        recurring_task_id = task_id.replace("recurring_", "")
        task_id = None

    if recurring_task_id:
        recurring_task = await db.get(RecurringTask, recurring_task_id)
        if not recurring_task or recurring_task.user_id != user.id:
            raise HTTPException(status_code=404, detail="Recurring task not found")

        existing_daily = await db.execute(
            select(DailyTask)
            .where(DailyTask.daily_plan_id == plan.id)
            .where(DailyTask.recurring_task_id == recurring_task.id)
        )
        existing_dt = existing_daily.scalar_one_or_none()
        if existing_dt:
            result = await db.execute(
                select(DailyTask)
                .where(DailyTask.id == existing_dt.id)
                .options(
                    selectinload(DailyTask.subtasks),
                    selectinload(DailyTask.task).selectinload(Task.project),
                    selectinload(DailyTask.task).selectinload(Task.description_attachments),
                    selectinload(DailyTask.recurring_task).selectinload(RecurringTask.project),
                    selectinload(DailyTask.recurring_task).selectinload(RecurringTask.description_attachments),
                    selectinload(DailyTask.timer_sessions),
                    selectinload(DailyTask.emotion_entries),
                )
            )
            return result.scalar_one()

        daily_task = DailyTask(
            user_id=plan.user_id,
            daily_plan_id=plan.id,
            recurring_task_id=recurring_task.id,
            title_snapshot=recurring_task.title,
            priority=priority,
            estimated_seconds=recurring_task.estimated_seconds,
            status=DailyTaskStatus.planned,
            sort_order=max_order + 1,
        )
        db.add(daily_task)
        await db.flush()
        await carry_over_subtasks(db, daily_task)

        today_start = datetime(plan.date.year, plan.date.month, plan.date.day, 0, 0, 0)
        existing_instance_result = await db.execute(
            select(RecurringTaskInstance)
            .where(RecurringTaskInstance.recurring_task_id == recurring_task.id)
            .where(RecurringTaskInstance.date == today_start)
        )
        existing_instance = existing_instance_result.scalar_one_or_none()
        if existing_instance:
            existing_instance.daily_task_id = daily_task.id
        else:
            instance = RecurringTaskInstance(
                user_id=plan.user_id,
                recurring_task_id=recurring_task.id,
                date=today_start,
                daily_task_id=daily_task.id,
                status=RecurringInstanceStatus.pending,
            )
            db.add(instance)
    else:
        task = await db.get(Task, task_id)
        if not task or task.user_id != user.id:
            raise HTTPException(status_code=404, detail="Task not found")

        existing_daily = await db.execute(
            select(DailyTask)
            .where(DailyTask.daily_plan_id == plan.id)
            .where(DailyTask.task_id == task.id)
        )
        existing_dt = existing_daily.scalar_one_or_none()
        if existing_dt:
            await sync_base_task_status(db, task.id, TaskStatus.active)
            result = await db.execute(
                select(DailyTask)
                .where(DailyTask.id == existing_dt.id)
                .options(
                    selectinload(DailyTask.subtasks),
                    selectinload(DailyTask.task).selectinload(Task.project),
                    selectinload(DailyTask.task).selectinload(Task.description_attachments),
                    selectinload(DailyTask.timer_sessions),
                    selectinload(DailyTask.emotion_entries),
                )
            )
            return result.scalar_one()

        daily_task = DailyTask(
            user_id=plan.user_id,
            daily_plan_id=plan.id,
            task_id=task.id,
            title_snapshot=task.title,
            priority=priority,
            estimated_seconds=task.estimated_seconds,
            status=DailyTaskStatus.planned,
            sort_order=max_order + 1,
        )
        db.add(daily_task)
        await sync_base_task_status(db, task.id, TaskStatus.active)
        await db.flush()
        await carry_over_subtasks(db, daily_task)

    await db.commit()
    
    result = await db.execute(
        select(DailyTask)
        .where(DailyTask.id == daily_task.id)
        .options(
            selectinload(DailyTask.subtasks),
            selectinload(DailyTask.task).selectinload(Task.project),
            selectinload(DailyTask.task).selectinload(Task.description_attachments),
            selectinload(DailyTask.recurring_task).selectinload(RecurringTask.project),
            selectinload(DailyTask.recurring_task).selectinload(RecurringTask.description_attachments),
            selectinload(DailyTask.timer_sessions),
            selectinload(DailyTask.emotion_entries),
        )
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


@router.get("/today/suggestions")
async def get_suggestions(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.recurring_engine import get_tasks_for_date
    
    today = local_today()
    yesterday = today - timedelta(days=1)

    today_plan_result = await db.execute(
        select(DailyPlan).where(DailyPlan.date == today, DailyPlan.user_id == user.id)
    )
    today_plan = today_plan_result.scalar_one_or_none()

    existing_task_ids_in_plan = set()
    existing_recurring_in_plan = set()
    if today_plan:
        existing_daily_result = await db.execute(
            select(DailyTask.task_id, DailyTask.recurring_task_id)
            .where(DailyTask.daily_plan_id == today_plan.id, DailyTask.user_id == user.id)
        )
        for task_id, recurring_task_id in existing_daily_result.all():
            if task_id:
                existing_task_ids_in_plan.add(task_id)
            if recurring_task_id:
                existing_recurring_in_plan.add(recurring_task_id)

    rolled_over_result = await db.execute(
        select(DailyTask)
        .join(DailyPlan)
        .where(DailyPlan.date == yesterday, DailyPlan.user_id == user.id)
        .where(DailyTask.status == DailyTaskStatus.rolled_over)
        .options(
            selectinload(DailyTask.task).selectinload(Task.project),
            selectinload(DailyTask.task).selectinload(Task.description_attachments),
            selectinload(DailyTask.recurring_task).selectinload(RecurringTask.project),
            selectinload(DailyTask.recurring_task).selectinload(RecurringTask.description_attachments),
        )
    )
    rolled_over_tasks = [
        daily_task
        for daily_task in rolled_over_result.scalars().all()
        if (
            daily_task.task_id and daily_task.task_id not in existing_task_ids_in_plan
        ) or (
            daily_task.recurring_task_id and daily_task.recurring_task_id not in existing_recurring_in_plan
        )
    ]

    high_priority_query = (
        select(Task)
        .where(Task.status == TaskStatus.backlog, Task.user_id == user.id)
        .where(Task.priority.in_(["critical", "high"]))
        .options(selectinload(Task.description_attachments))
        .order_by(Task.priority, Task.created_at.desc())
        .limit(10)
    )
    if existing_task_ids_in_plan:
        high_priority_query = high_priority_query.where(Task.id.notin_(existing_task_ids_in_plan))
    high_priority_result = await db.execute(high_priority_query)
    high_priority_tasks = high_priority_result.scalars().all()

    due_today_query = (
        select(Task)
        .where(Task.status == TaskStatus.backlog, Task.user_id == user.id)
        .where(Task.due_date == today)
        .options(selectinload(Task.description_attachments))
    )
    if existing_task_ids_in_plan:
        due_today_query = due_today_query.where(Task.id.notin_(existing_task_ids_in_plan))
    due_today_result = await db.execute(due_today_query)
    due_today_tasks = due_today_result.scalars().all()

    recurring_result = await db.execute(
        select(RecurringTask)
        .where(RecurringTask.is_active == True, RecurringTask.user_id == user.id)
        .options(selectinload(RecurringTask.project), selectinload(RecurringTask.description_attachments))
    )
    all_recurring = recurring_result.scalars().all()
    matching_recurring = get_tasks_for_date(all_recurring, today)

    recurring_suggestions = [rt for rt in matching_recurring if rt.id not in existing_recurring_in_plan]

    def task_to_dict(t):
        project_id = None
        source_task = None
        suggestion_id = str(t.id)
        is_daily_task = hasattr(t, 'daily_plan_id')
        if hasattr(t, 'task_id') and t.task_id and hasattr(t, 'task') and t.task:
            source_task = t.task
            suggestion_id = str(t.task_id)
            project_id = str(t.task.project_id)
        elif is_daily_task and getattr(t, 'recurring_task_id', None):
            source_task = getattr(t, 'recurring_task', None)
            suggestion_id = f"recurring_{t.recurring_task_id}"
            project_id = str(source_task.project_id) if source_task else None
        elif hasattr(t, 'project_id') and t.project_id:
            source_task = t
            project_id = str(t.project_id)
        return {
            "id": suggestion_id,
            "project_id": project_id,
            "title": t.title_snapshot if hasattr(t, 'title_snapshot') else t.title,
            "description": getattr(source_task, 'description', None),
            "description_doc": getattr(source_task, 'description_doc', None),
            "description_attachments": [
                {
                    "id": str(att.id),
                    "kind": att.kind,
                    "file_name": att.file_name,
                    "mime_type": att.mime_type,
                    "size_bytes": att.size_bytes,
                }
                for att in getattr(source_task, 'description_attachments', [])
            ] if source_task else [],
            "source": "manual",
            "external_key": t.external_key if hasattr(t, 'external_key') else None,
            "external_url": t.external_url if hasattr(t, 'external_url') else None,
            "status": t.status.value if hasattr(t.status, 'value') else t.status,
            "priority": t.priority.value if hasattr(t.priority, 'value') else t.priority,
            "due_date": str(source_task.due_date) if source_task and getattr(source_task, 'due_date', None) else None,
            "estimated_seconds": getattr(source_task, 'estimated_seconds', None),
            "category": t.category if hasattr(t, 'category') else getattr(source_task, 'category', None),
            "meeting_time": str(source_task.meeting_time) if source_task and getattr(source_task, 'meeting_time', None) else None,
            "tag": getattr(t, 'tag', None),
            "created_at": str(t.started_at) if hasattr(t, 'started_at') and t.started_at else None,
            "updated_at": str(t.completed_at) if hasattr(t, 'completed_at') and t.completed_at else None,
        }

    def recurring_to_dict(rt):
        project_id = str(rt.project_id)
        if hasattr(rt, 'project') and rt.project:
            project_id = str(rt.project.id)
        return {
            "id": f"recurring_{rt.id}",
            "project_id": project_id,
            "title": rt.title,
            "description": rt.description,
            "description_doc": rt.description_doc,
            "description_attachments": [
                {
                    "id": str(att.id),
                    "kind": att.kind,
                    "file_name": att.file_name,
                    "mime_type": att.mime_type,
                    "size_bytes": att.size_bytes,
                }
                for att in getattr(rt, 'description_attachments', [])
            ],
            "source": "manual",
            "external_key": None,
            "external_url": rt.external_url,
            "status": "backlog",
            "priority": rt.priority.value if hasattr(rt.priority, 'value') else rt.priority,
            "due_date": None,
            "estimated_seconds": rt.estimated_seconds,
            "category": rt.category,
            "meeting_time": str(rt.meeting_time) if rt.meeting_time else None,
            "tag": rt.tag,
            "created_at": str(rt.created_at),
            "updated_at": str(rt.updated_at),
            "is_recurring": True,
        }

    return {
        "rolled_over": [task_to_dict(t) for t in rolled_over_tasks],
        "high_priority_backlog": [task_to_dict(t) for t in high_priority_tasks],
        "due_today": [task_to_dict(t) for t in due_today_tasks],
        "recurring_today": [recurring_to_dict(rt) for rt in recurring_suggestions],
    }


@router.post("/{plan_id}/close")
async def close_plan(
    plan_id: UUID,
    data: DailyPlanCloseRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plan = await db.get(DailyPlan, plan_id)
    if not plan or plan.user_id != user.id:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status == DailyPlanStatus.closed:
        raise HTTPException(status_code=400, detail="Plan is already closed")

    reflection = None
    if data and data.reflection:
        reflection_payload = data.reflection.model_dump(exclude_unset=True)
        if _has_reflection_content(reflection_payload):
            reflection = await _save_optional_reflection(db, plan, reflection_payload)

    summary = await close_day_service(db, plan)
    return {
        "plan_id": str(plan.id),
        "date": str(plan.date),
        "status": plan.status.value if hasattr(plan.status, 'value') else plan.status,
        "summary": summary,
        "reflection": {
            "id": str(reflection.id),
            "daily_plan_id": str(reflection.daily_plan_id),
        } if reflection else None,
    }


@router.post("/{plan_id}/reopen")
async def reopen_plan(plan_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    plan = await db.get(DailyPlan, plan_id)
    if not plan or plan.user_id != user.id:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status == DailyPlanStatus.open:
        raise HTTPException(status_code=400, detail="Plan is already open")

    plan.status = DailyPlanStatus.open

    result = await db.execute(
        select(DailyTask).where(DailyTask.daily_plan_id == plan.id)
    )
    tasks = result.scalars().all()
    reopened = 0
    for task in tasks:
        if task.status in [DailyTaskStatus.rolled_over, DailyTaskStatus.skipped]:
            task.status = DailyTaskStatus.planned
            await sync_base_task_status(db, task.task_id, TaskStatus.active)
            reopened += 1

    await db.flush()

    return {
        "plan_id": str(plan.id),
        "date": str(plan.date),
        "status": "open",
        "reopened_tasks": reopened,
    }
