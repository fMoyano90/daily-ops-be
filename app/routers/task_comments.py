from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_db
from app.models.task import Task
from app.models.recurring_task import RecurringTask
from app.models.task_comment import TaskComment
from app.schemas.task_comment import TaskCommentCreate, TaskCommentUpdate, TaskCommentResponse

router = APIRouter(prefix="/api/v1", tags=["task-comments"])


async def _list_for(db: AsyncSession, *, task_id: UUID | None = None, recurring_task_id: UUID | None = None):
    query = select(TaskComment).order_by(TaskComment.created_at.desc())
    if task_id:
        query = query.where(TaskComment.task_id == task_id)
    else:
        query = query.where(TaskComment.recurring_task_id == recurring_task_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/tasks/{task_id}/comments", response_model=list[TaskCommentResponse])
async def list_task_comments(task_id: UUID, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return await _list_for(db, task_id=task_id)


@router.post("/tasks/{task_id}/comments", response_model=TaskCommentResponse, status_code=status.HTTP_201_CREATED)
async def create_task_comment(task_id: UUID, data: TaskCommentCreate, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    comment = TaskComment(task_id=task_id, content=data.content)
    db.add(comment)
    await db.flush()
    await db.refresh(comment)
    return comment


@router.get("/recurring-tasks/{recurring_task_id}/comments", response_model=list[TaskCommentResponse])
async def list_recurring_task_comments(recurring_task_id: UUID, db: AsyncSession = Depends(get_db)):
    rt = await db.get(RecurringTask, recurring_task_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Recurring task not found")
    return await _list_for(db, recurring_task_id=recurring_task_id)


@router.post(
    "/recurring-tasks/{recurring_task_id}/comments",
    response_model=TaskCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_recurring_task_comment(
    recurring_task_id: UUID, data: TaskCommentCreate, db: AsyncSession = Depends(get_db)
):
    rt = await db.get(RecurringTask, recurring_task_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Recurring task not found")
    comment = TaskComment(recurring_task_id=recurring_task_id, content=data.content)
    db.add(comment)
    await db.flush()
    await db.refresh(comment)
    return comment


@router.patch("/task-comments/{comment_id}", response_model=TaskCommentResponse)
async def update_comment(comment_id: UUID, data: TaskCommentUpdate, db: AsyncSession = Depends(get_db)):
    comment = await db.get(TaskComment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    comment.content = data.content
    await db.flush()
    await db.refresh(comment)
    return comment


@router.delete("/task-comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(comment_id: UUID, db: AsyncSession = Depends(get_db)):
    comment = await db.get(TaskComment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    await db.delete(comment)
    await db.flush()
