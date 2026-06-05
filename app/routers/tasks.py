from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime, timezone
from uuid import UUID

from app.database import get_db
from app.dependencies import get_current_user
from app.models.task import Task, TaskStatus, TaskSource, Priority
from app.models.task_description_attachment import TaskDescriptionAttachment
from app.models.recurring_task import RecurringTask, RecurringTaskInstance, RecurringInstanceStatus, RecurringTaskType
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from app.schemas.rich_text import RichTextAttachmentResponse, plain_text_to_rich_text, rich_text_to_plain_text
from app.services.azure_storage import delete_capture_file, get_blob_download_url, upload_task_description_file
from app.utils.timezone import local_today
import calendar

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _description_payload(payload: dict) -> dict:
    if "description_doc" in payload:
        payload["description"] = rich_text_to_plain_text(payload.get("description_doc")) if payload.get("description_doc") is not None else None
        payload["description_customized_at"] = datetime.now(timezone.utc)
    elif payload.get("description") and "description_doc" not in payload:
        payload["description_doc"] = plain_text_to_rich_text(payload.get("description"))
    return payload


async def _get_task_for_response(db: AsyncSession, task_id: UUID, user_id: UUID) -> Task | None:
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id, Task.user_id == user_id)
        .options(selectinload(Task.description_attachments))
    )
    return result.scalar_one_or_none()


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
    query = select(Task).where(Task.user_id == user.id).options(selectinload(Task.description_attachments))
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
    today = local_today()
    today_start = datetime(today.year, today.month, today.day, 0, 0, 0)
    today_end = datetime(today.year, today.month, today.day, 23, 59, 59)

    result = await db.execute(
        select(Task)
        .where(Task.status == TaskStatus.backlog, Task.user_id == user.id)
        .options(selectinload(Task.description_attachments))
        .order_by(Task.priority, Task.created_at.desc())
    )
    backlog_tasks = result.scalars().all()

    skipped_recurring_result = await db.execute(
        select(RecurringTaskInstance)
        .join(RecurringTask)
        .where(RecurringTaskInstance.status == RecurringInstanceStatus.skipped)
        .where(RecurringTaskInstance.date >= today_start)
        .where(RecurringTaskInstance.date <= today_end)
        .where(RecurringTask.user_id == user.id)
        .options(
            selectinload(RecurringTaskInstance.recurring_task).selectinload(RecurringTask.project),
            selectinload(RecurringTaskInstance.recurring_task).selectinload(RecurringTask.description_attachments),
        )
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
            "description_doc": task.description_doc,
            "description_attachments": [
                {
                    "id": str(att.id),
                    "kind": att.kind,
                    "file_name": att.file_name,
                    "mime_type": att.mime_type,
                    "size_bytes": att.size_bytes,
                }
                for att in task.description_attachments
            ],
            "source": task.source.value if hasattr(task.source, 'value') else task.source,
            "external_key": task.external_key,
            "external_url": task.external_url,
            "status": task.status.value if hasattr(task.status, 'value') else task.status,
            "priority": task.priority.value if hasattr(task.priority, 'value') else task.priority,
            "due_date": str(task.due_date) if task.due_date else None,
            "estimated_seconds": task.estimated_seconds,
            "category": task.category,
            "meeting_time": str(task.meeting_time) if task.meeting_time else None,
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
            "description_doc": rt.description_doc,
            "description_attachments": [
                {
                    "id": str(att.id),
                    "kind": att.kind,
                    "file_name": att.file_name,
                    "mime_type": att.mime_type,
                    "size_bytes": att.size_bytes,
                }
                for att in getattr(rt, "description_attachments", [])
            ],
            "source": "recurring",
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
            "recurring_task_id": str(rt.id),
        })

    combined.sort(key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x["priority"], 4))

    return combined


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(data: TaskCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    payload = _description_payload(data.model_dump(exclude_unset=True))
    task = Task(**payload, user_id=user.id)
    db.add(task)
    await db.flush()
    result = await _get_task_for_response(db, task.id, user.id)
    return result


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await _get_task_for_response(db, task_id, user.id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: UUID, data: TaskUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await db.get(Task, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    update_data = _description_payload(data.model_dump(exclude_unset=True))
    for key, value in update_data.items():
        setattr(task, key, value)
    await db.flush()
    result = await _get_task_for_response(db, task_id, user.id)
    return result


@router.post("/{task_id}/description-attachments", response_model=RichTextAttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_description_attachment(
    task_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")

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
        task_id=task.id,
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
            TaskDescriptionAttachment.task_id == task_id,
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
            TaskDescriptionAttachment.task_id == task_id,
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


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await db.get(Task, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.flush()
