from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_db
from app.models.daily_task import DailyTask
from app.models.daily_subtask import DailySubtask
from app.schemas.daily_subtask import DailySubtaskCreate, DailySubtaskUpdate, DailySubtaskResponse

router = APIRouter(prefix="/api/v1/daily-tasks/{daily_task_id}/subtasks", tags=["subtasks"])


@router.get("", response_model=list[DailySubtaskResponse])
async def list_subtasks(daily_task_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DailySubtask)
        .where(DailySubtask.daily_task_id == daily_task_id)
        .order_by(DailySubtask.sort_order)
    )
    return result.scalars().all()


@router.post("", response_model=DailySubtaskResponse, status_code=status.HTTP_201_CREATED)
async def create_subtask(daily_task_id: UUID, data: DailySubtaskCreate, db: AsyncSession = Depends(get_db)):
    task = await db.get(DailyTask, daily_task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Daily task not found")

    result = await db.execute(
        select(DailySubtask).where(DailySubtask.daily_task_id == daily_task_id)
    )
    existing = result.scalars().all()
    max_order = max([s.sort_order for s in existing], default=0)

    subtask = DailySubtask(
        daily_task_id=daily_task_id,
        **data.model_dump(),
        sort_order=max_order + 1,
    )
    db.add(subtask)
    await db.flush()
    await db.refresh(subtask)
    return subtask


@router.patch("/{subtask_id}", response_model=DailySubtaskResponse)
async def update_subtask(daily_task_id: UUID, subtask_id: UUID, data: DailySubtaskUpdate, db: AsyncSession = Depends(get_db)):
    subtask = await db.get(DailySubtask, subtask_id)
    if not subtask or subtask.daily_task_id != daily_task_id:
        raise HTTPException(status_code=404, detail="Subtask not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(subtask, key, value)

    await db.flush()
    await db.refresh(subtask)
    return subtask


@router.delete("/{subtask_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subtask(daily_task_id: UUID, subtask_id: UUID, db: AsyncSession = Depends(get_db)):
    subtask = await db.get(DailySubtask, subtask_id)
    if not subtask or subtask.daily_task_id != daily_task_id:
        raise HTTPException(status_code=404, detail="Subtask not found")
    await db.delete(subtask)
    await db.flush()
