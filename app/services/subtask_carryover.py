import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_plan import DailyPlan
from app.models.daily_task import DailyTask
from app.models.daily_subtask import DailySubtask


async def carry_over_subtasks(db: AsyncSession, new_daily_task: DailyTask) -> int:
    new_plan = await db.get(DailyPlan, new_daily_task.daily_plan_id)
    if not new_plan:
        return 0

    query = (
        select(DailyTask)
        .join(DailyPlan, DailyTask.daily_plan_id == DailyPlan.id)
        .where(DailyTask.user_id == new_daily_task.user_id)
        .where(DailyTask.id != new_daily_task.id)
        .where(DailyPlan.date < new_plan.date)
        .options(selectinload(DailyTask.subtasks))
        .order_by(DailyPlan.date.desc())
        .limit(1)
    )
    if new_daily_task.task_id is not None:
        query = query.where(DailyTask.task_id == new_daily_task.task_id)
    elif new_daily_task.recurring_task_id is not None:
        query = query.where(DailyTask.recurring_task_id == new_daily_task.recurring_task_id)
    else:
        return 0

    result = await db.execute(query)
    prior = result.scalar_one_or_none()
    if not prior or not prior.subtasks:
        return 0

    for sub in prior.subtasks:
        db.add(DailySubtask(
            id=uuid.uuid4(),
            user_id=new_daily_task.user_id,
            daily_task_id=new_daily_task.id,
            title=sub.title,
            status=sub.status,
            priority=sub.priority,
            sort_order=sub.sort_order,
        ))
    return len(prior.subtasks)
