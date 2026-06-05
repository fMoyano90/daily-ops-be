from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime, timezone
from uuid import UUID

from app.database import get_db
from app.dependencies import get_current_user
from app.models.recurring_task import RecurringTask, RecurringTaskInstance, RecurringInstanceStatus
from app.models.project import Project
from app.models.task_description_attachment import TaskDescriptionAttachment
from app.models.user import User
from app.schemas.recurring_task import (
    RecurringTaskCreate,
    RecurringTaskUpdate,
    RecurringTaskResponse,
    RecurringInstanceResponse,
)
from app.services.recurring_engine import get_history_for_task
from app.schemas.rich_text import RichTextAttachmentResponse, plain_text_to_rich_text, rich_text_to_plain_text
from app.services.azure_storage import delete_capture_file, get_blob_download_url, upload_task_description_file

router = APIRouter(prefix="/api/v1/recurring-tasks", tags=["recurring-tasks"])

ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _description_payload(payload: dict) -> dict:
    if "description_doc" in payload:
        payload["description"] = rich_text_to_plain_text(payload.get("description_doc")) if payload.get("description_doc") is not None else None
        payload["description_customized_at"] = datetime.now(timezone.utc)
    elif payload.get("description") and "description_doc" not in payload:
        payload["description_doc"] = plain_text_to_rich_text(payload.get("description"))
    return payload


def _recurring_options():
    return (selectinload(RecurringTask.project), selectinload(RecurringTask.description_attachments))


@router.get("", response_model=list[RecurringTaskResponse])
async def list_recurring_tasks(
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(RecurringTask).where(RecurringTask.user_id == user.id).options(*_recurring_options())
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
    user: User = Depends(get_current_user),
):
    project = await db.get(Project, data.project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    task = RecurringTask(**_description_payload(data.model_dump(exclude_unset=True)), user_id=user.id)
    db.add(task)
    await db.flush()
    await db.refresh(task)

    result = await db.execute(
        select(RecurringTask)
        .where(RecurringTask.id == task.id)
        .options(*_recurring_options())
    )
    return RecurringTaskResponse.from_orm_with_stats(result.scalar_one())


@router.get("/{task_id}", response_model=RecurringTaskResponse)
async def get_recurring_task(task_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(RecurringTask)
        .where(RecurringTask.id == task_id, RecurringTask.user_id == user.id)
        .options(*_recurring_options())
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
    user: User = Depends(get_current_user),
):
    task = await db.get(RecurringTask, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Recurring task not found")

    update_data = _description_payload(data.model_dump(exclude_unset=True))
    if "project_id" in update_data:
        project = await db.get(Project, update_data["project_id"])
        if not project or project.user_id != user.id:
            raise HTTPException(status_code=404, detail="Project not found")

    for key, value in update_data.items():
        setattr(task, key, value)

    await db.flush()
    await db.refresh(task)

    result = await db.execute(
        select(RecurringTask)
        .where(RecurringTask.id == task_id)
        .options(*_recurring_options())
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
async def delete_recurring_task(task_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await db.get(RecurringTask, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Recurring task not found")

    task.is_active = False
    await db.flush()


@router.post("/{task_id}/description-attachments", response_model=RichTextAttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_description_attachment(
    task_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = await db.get(RecurringTask, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Recurring task not found")

    mime = file.content_type or ""
    if mime not in ALLOWED_IMAGE_MIMES:
        raise HTTPException(status_code=422, detail=f"Unsupported file type: {mime}")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=422, detail="File too large. Max 8MB for image")

    try:
        storage_path = upload_task_description_file(user.id, file_bytes, file.filename or "upload", mime)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Azure Storage is not configured. Please set AZURE_STORAGE_CONNECTION_STRING.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(exc)}")

    attachment = TaskDescriptionAttachment(
        recurring_task_id=task.id,
        user_id=user.id,
        kind="image",
        file_name=file.filename or "upload",
        mime_type=mime,
        size_bytes=len(file_bytes),
        storage_path=storage_path,
    )
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)
    return attachment


@router.get("/{task_id}/description-attachments/{attachment_id}/url", response_model=dict)
async def get_description_attachment_url(
    task_id: UUID,
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TaskDescriptionAttachment).where(
            TaskDescriptionAttachment.id == attachment_id,
            TaskDescriptionAttachment.recurring_task_id == task_id,
            TaskDescriptionAttachment.user_id == user.id,
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    try:
        url = get_blob_download_url(attachment.storage_path)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Azure Storage is not configured. Please set AZURE_STORAGE_CONNECTION_STRING.")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Attachment file not found in storage")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {str(exc)}")
    return {"url": url, "mime_type": attachment.mime_type, "file_name": attachment.file_name}


@router.delete("/{task_id}/description-attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_description_attachment(
    task_id: UUID,
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TaskDescriptionAttachment).where(
            TaskDescriptionAttachment.id == attachment_id,
            TaskDescriptionAttachment.recurring_task_id == task_id,
            TaskDescriptionAttachment.user_id == user.id,
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    try:
        delete_capture_file(attachment.storage_path)
    except Exception:
        pass
    await db.delete(attachment)
    await db.flush()


@router.get("/{task_id}/history", response_model=list[RecurringInstanceResponse])
async def get_task_history(
    task_id: UUID,
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = await db.get(RecurringTask, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Recurring task not found")

    instances = await get_history_for_task(db, str(task_id), limit)
    return instances
