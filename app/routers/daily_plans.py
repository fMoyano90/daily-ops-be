from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from app.database import get_db
from app.models.daily_plan import DailyPlan, DailyPlanStatus
from app.models.daily_task import DailyTask, DailyTaskStatus
from app.models.task import Task, TaskStatus
from app.models.project import Project
from app.models.recurring_task import RecurringTask, RecurringTaskInstance, RecurringInstanceStatus
from app.schemas.daily_plan import DailyPlanCreate, DailyPlanUpdate, DailyPlanResponse
from app.schemas.daily_task import DailyTaskResponse
from app.schemas.project import ProjectResponse
from app.schemas.task import TaskResponse
from app.services.day_closer import close_day_service
from app.services.recurring_engine import auto_add_for_today

router = APIRouter(prefix="/api/v1/daily-plans", tags=["daily-plans"])


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


@router.get("/today", response_model=DailyPlanResponse)
async def get_today_plan(db: AsyncSession = Depends(get_db)):
    today = date.today()
    result = await db.execute(
        select(DailyPlan)
        .where(DailyPlan.date == today)
        .options(
            selectinload(DailyPlan.tasks)
            .selectinload(DailyTask.subtasks),
            selectinload(DailyPlan.tasks)
            .selectinload(DailyTask.task)
            .selectinload(Task.project),
            selectinload(DailyPlan.tasks)
            .selectinload(DailyTask.recurring_task).selectinload(RecurringTask.project),
            selectinload(DailyPlan.tasks)
            .selectinload(DailyTask.timer_sessions),
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        plan = DailyPlan(date=today)
        db.add(plan)
        await db.commit()
        result = await db.execute(
            select(DailyPlan)
            .where(DailyPlan.date == today)
            .options(
                selectinload(DailyPlan.tasks)
                .selectinload(DailyTask.subtasks),
                selectinload(DailyPlan.tasks)
                .selectinload(DailyTask.task)
                .selectinload(Task.project),
                selectinload(DailyPlan.tasks)
                .selectinload(DailyTask.recurring_task),
                selectinload(DailyPlan.tasks)
                .selectinload(DailyTask.timer_sessions),
            )
        )
        plan = result.scalar_one()

    await auto_add_for_today(db, plan)

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
            .selectinload(DailyTask.recurring_task).selectinload(RecurringTask.project),
            selectinload(DailyPlan.tasks)
            .selectinload(DailyTask.timer_sessions),
        )
    )
    return inject_live_seconds(result.scalar_one())


@router.get("/{plan_date}", response_model=DailyPlanResponse)
async def get_plan_by_date(plan_date: date, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DailyPlan).where(DailyPlan.date == plan_date))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found for this date")
    return plan


@router.post("", response_model=DailyPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_daily_plan(data: DailyPlanCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DailyPlan).where(DailyPlan.date == data.date))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Plan already exists for this date")
    plan = DailyPlan(**data.model_dump())
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return plan


@router.post("/today/tasks", response_model=DailyPlanResponse, status_code=status.HTTP_201_CREATED)
async def select_tasks_for_today(task_ids: list[UUID], db: AsyncSession = Depends(get_db)):
    today = date.today()
    result = await db.execute(select(DailyPlan).where(DailyPlan.date == today))
    plan = result.scalar_one_or_none()
    if not plan:
        plan = DailyPlan(date=today)
        db.add(plan)
        await db.flush()
        await db.refresh(plan)

    existing_result = await db.execute(select(DailyTask).where(DailyTask.daily_plan_id == plan.id))
    existing_tasks = existing_result.scalars().all()
    max_order = max([t.sort_order for t in existing_tasks], default=0)

    added = []
    for i, task_id in enumerate(task_ids):
        task = await db.get(Task, task_id)
        if not task:
            continue
        daily_task = DailyTask(
            daily_plan_id=plan.id,
            task_id=task.id,
            title_snapshot=task.title,
            priority=task.priority,
            status=DailyTaskStatus.planned,
            sort_order=max_order + i + 1,
        )
        db.add(daily_task)
        added.append(daily_task)

    await db.flush()
    for dt in added:
        await db.refresh(dt)

    await db.refresh(plan)
    return plan


@router.post("/{plan_id}/tasks", response_model=DailyTaskResponse, status_code=status.HTTP_201_CREATED)
async def add_task_to_plan(plan_id: UUID, data: dict, db: AsyncSession = Depends(get_db)):
    plan = await db.get(DailyPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    task_id = data.get("task_id")
    recurring_task_id = data.get("recurring_task_id")
    priority = data.get("priority", "medium")

    result = await db.execute(select(DailyTask).where(DailyTask.daily_plan_id == plan_id))
    existing = result.scalars().all()
    max_order = max([t.sort_order for t in existing], default=0)

    if task_id and task_id.startswith("recurring_"):
        recurring_task_id = task_id.replace("recurring_", "")
        task_id = None

    if recurring_task_id:
        recurring_task = await db.get(RecurringTask, recurring_task_id)
        if not recurring_task:
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
                    selectinload(DailyTask.recurring_task).selectinload(RecurringTask.project),
                )
            )
            return result.scalar_one()

        daily_task = DailyTask(
            daily_plan_id=plan.id,
            recurring_task_id=recurring_task.id,
            title_snapshot=recurring_task.title,
            priority=priority,
            status=DailyTaskStatus.planned,
            sort_order=max_order + 1,
        )
        db.add(daily_task)
        await db.flush()

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
                recurring_task_id=recurring_task.id,
                date=today_start,
                daily_task_id=daily_task.id,
                status=RecurringInstanceStatus.pending,
            )
            db.add(instance)
    else:
        task = await db.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        existing_daily = await db.execute(
            select(DailyTask)
            .where(DailyTask.daily_plan_id == plan.id)
            .where(DailyTask.task_id == task.id)
        )
        existing_dt = existing_daily.scalar_one_or_none()
        if existing_dt:
            result = await db.execute(
                select(DailyTask)
                .where(DailyTask.id == existing_dt.id)
                .options(
                    selectinload(DailyTask.subtasks),
                    selectinload(DailyTask.task).selectinload(Task.project),
                )
            )
            return result.scalar_one()

        daily_task = DailyTask(
            daily_plan_id=plan.id,
            task_id=task.id,
            title_snapshot=task.title,
            priority=priority,
            status=DailyTaskStatus.planned,
            sort_order=max_order + 1,
        )
        db.add(daily_task)

    await db.commit()
    
    result = await db.execute(
        select(DailyTask)
        .where(DailyTask.id == daily_task.id)
        .options(
            selectinload(DailyTask.subtasks),
            selectinload(DailyTask.task).selectinload(Task.project),
            selectinload(DailyTask.recurring_task).selectinload(RecurringTask.project),
        )
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


@router.get("/today/suggestions")
async def get_suggestions(db: AsyncSession = Depends(get_db)):
    from app.services.recurring_engine import get_tasks_for_date
    
    today = date.today()
    yesterday = today - timedelta(days=1)

    rolled_over_result = await db.execute(
        select(DailyTask)
        .join(DailyPlan)
        .where(DailyPlan.date == yesterday)
        .where(DailyTask.status.in_([DailyTaskStatus.in_progress, DailyTaskStatus.paused, DailyTaskStatus.planned]))
    )
    rolled_over_tasks = rolled_over_result.scalars().all()

    high_priority_result = await db.execute(
        select(Task)
        .where(Task.status == TaskStatus.backlog)
        .where(Task.priority.in_(["critical", "high"]))
        .order_by(Task.priority, Task.created_at.desc())
        .limit(10)
    )
    high_priority_tasks = high_priority_result.scalars().all()

    due_today_result = await db.execute(
        select(Task)
        .where(Task.status == TaskStatus.backlog)
        .where(Task.due_date == today)
    )
    due_today_tasks = due_today_result.scalars().all()

    recurring_result = await db.execute(
        select(RecurringTask)
        .where(RecurringTask.is_active == True)
        .options(selectinload(RecurringTask.project))
    )
    all_recurring = recurring_result.scalars().all()
    matching_recurring = get_tasks_for_date(all_recurring, today)

    today_plan_result = await db.execute(
        select(DailyPlan).where(DailyPlan.date == today)
    )
    today_plan = today_plan_result.scalar_one_or_none()
    
    existing_recurring_in_plan = set()
    if today_plan:
        existing_daily_result = await db.execute(
            select(DailyTask.recurring_task_id)
            .where(DailyTask.daily_plan_id == today_plan.id)
            .where(DailyTask.recurring_task_id.isnot(None))
        )
        existing_recurring_in_plan = {row[0] for row in existing_daily_result.all()}

    recurring_suggestions = [rt for rt in matching_recurring if rt.id not in existing_recurring_in_plan]

    def task_to_dict(t):
        return {
            "id": str(t.id),
            "project_id": str(t.project_id),
            "title": t.title,
            "description": t.description,
            "source": t.source.value if hasattr(t.source, 'value') else t.source,
            "external_key": t.external_key,
            "external_url": t.external_url,
            "status": t.status.value if hasattr(t.status, 'value') else t.status,
            "priority": t.priority.value if hasattr(t.priority, 'value') else t.priority,
            "due_date": str(t.due_date) if t.due_date else None,
            "category": t.category,
            "created_at": str(t.created_at),
            "updated_at": str(t.updated_at),
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
            "source": "manual",
            "external_key": None,
            "external_url": None,
            "status": "backlog",
            "priority": rt.priority.value if hasattr(rt.priority, 'value') else rt.priority,
            "due_date": None,
            "category": rt.category,
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
async def close_plan(plan_id: UUID, db: AsyncSession = Depends(get_db)):
    plan = await db.get(DailyPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status == DailyPlanStatus.closed:
        raise HTTPException(status_code=400, detail="Plan is already closed")

    summary = await close_day_service(db, plan)
    return {
        "plan_id": str(plan.id),
        "date": str(plan.date),
        "status": plan.status.value if hasattr(plan.status, 'value') else plan.status,
        "summary": summary,
    }


@router.post("/{plan_id}/reopen")
async def reopen_plan(plan_id: UUID, db: AsyncSession = Depends(get_db)):
    plan = await db.get(DailyPlan, plan_id)
    if not plan:
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
            reopened += 1

    await db.flush()

    return {
        "plan_id": str(plan.id),
        "date": str(plan.date),
        "status": "open",
        "reopened_tasks": reopened,
    }
