from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_plan import DailyPlan, DailyPlanStatus
from app.models.daily_task import DailyTask, DailyTaskStatus
from app.models.task import Task, TaskStatus


ACTIVE_DAILY_STATUSES = (
    DailyTaskStatus.planned,
    DailyTaskStatus.in_progress,
    DailyTaskStatus.paused,
)


async def sync_base_task_status(db: AsyncSession, task_id: UUID | None, target_status: TaskStatus) -> None:
    if not task_id:
        return
    base_task = await db.get(Task, task_id)
    if base_task and base_task.status != TaskStatus.archived:
        base_task.status = target_status


async def move_base_task_to_backlog_if_unused(
    db: AsyncSession,
    task_id: UUID | None,
    *,
    excluding_daily_task_id: UUID | None = None,
) -> bool:
    if not task_id:
        return False

    base_task = await db.get(Task, task_id)
    if not base_task or base_task.status != TaskStatus.active:
        return False

    query = (
        select(func.count(DailyTask.id))
        .join(DailyPlan, DailyPlan.id == DailyTask.daily_plan_id)
        .where(
            DailyTask.task_id == task_id,
            DailyTask.status.in_(ACTIVE_DAILY_STATUSES),
            DailyPlan.status == DailyPlanStatus.open,
        )
    )
    if excluding_daily_task_id:
        query = query.where(DailyTask.id != excluding_daily_task_id)

    result = await db.execute(query)
    if int(result.scalar_one() or 0) == 0:
        base_task.status = TaskStatus.backlog
        return True
    return False
