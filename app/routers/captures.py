import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, attributes

from app.database import get_db
from app.dependencies import get_current_user
from app.models.capture import Capture, CaptureAttachment, CaptureType, CaptureStatus
from app.models.user import User
from app.schemas.capture import CaptureCreate, CaptureResponse, CaptureUpdate
from app.services.azure_storage import upload_capture_file, delete_capture_file, get_blob_download_url
from app.utils.timezone import local_today

router = APIRouter(prefix="/api/v1/captures", tags=["captures"])

ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_AUDIO_MIMES = {"audio/webm", "audio/mp4", "audio/m4a", "audio/mpeg", "audio/ogg"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_AUDIO_BYTES = 25 * 1024 * 1024


async def _get_capture_or_404(db: AsyncSession, user: User, capture_id: uuid.UUID) -> Capture:
    result = await db.execute(
        select(Capture)
        .where(Capture.id == capture_id, Capture.user_id == user.id)
        .options(selectinload(Capture.attachments))
    )
    capture = result.scalar_one_or_none()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")
    return capture


def _response(capture: Capture) -> CaptureResponse:
    return CaptureResponse.model_validate(capture)


@router.get("", response_model=list[CaptureResponse])
async def list_captures(
    status_filter: str | None = Query(None, alias="status"),
    type_filter: str | None = Query(None, alias="type"),
    tag: str | None = Query(None),
    q: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Capture).where(Capture.user_id == user.id).options(selectinload(Capture.attachments))

    if status_filter:
        try:
            query = query.where(Capture.status == CaptureStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status: {status_filter}")

    if type_filter:
        try:
            query = query.where(Capture.capture_type == CaptureType(type_filter))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid type: {type_filter}")

    if tag:
        query = query.where(Capture.tags.contains([tag]))

    if q:
        query = query.where(
            (Capture.title.ilike(f"%{q}%")) | (Capture.content.ilike(f"%{q}%")) | (Capture.source_url.ilike(f"%{q}%"))
        )

    if date_from:
        query = query.where(Capture.note_date >= date_from)
    if date_to:
        query = query.where(Capture.note_date <= date_to)

    result = await db.execute(query.order_by(Capture.note_date.desc(), Capture.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.get("/stats", response_model=dict)
async def capture_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Capture.status, Capture.capture_type)
        .where(Capture.user_id == user.id)
    )
    rows = result.all()

    by_status = {}
    by_type = {}
    for status_val, type_val in rows:
        by_status[status_val.value] = by_status.get(status_val.value, 0) + 1
        by_type[type_val.value] = by_type.get(type_val.value, 0) + 1

    return {"by_status": by_status, "by_type": by_type}


@router.post("", response_model=CaptureResponse, status_code=status.HTTP_201_CREATED)
async def create_capture(
    data: CaptureCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    note_date = data.note_date or local_today()
    capture_type = CaptureType(data.capture_type) if data.capture_type else CaptureType.text

    payload = data.model_dump(exclude={"capture_type", "note_date"}, exclude_unset=True)
    capture = Capture(
        user_id=user.id,
        capture_type=capture_type,
        note_date=note_date,
        **payload,
    )
    db.add(capture)
    await db.flush()
    attributes.set_committed_value(capture, "attachments", [])
    return _response(capture)


@router.get("/{capture_id}", response_model=CaptureResponse)
async def get_capture(
    capture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    capture = await _get_capture_or_404(db, user, capture_id)
    return _response(capture)


@router.patch("/{capture_id}", response_model=CaptureResponse)
async def update_capture(
    capture_id: uuid.UUID,
    data: CaptureUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    capture = await _get_capture_or_404(db, user, capture_id)
    payload = data.model_dump(exclude_unset=True)

    if "status" in payload:
        try:
            payload["status"] = CaptureStatus(payload["status"])
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status: {data.status}")

    for key, value in payload.items():
        setattr(capture, key, value)

    await db.flush()
    await db.refresh(capture)
    return _response(capture)


@router.delete("/{capture_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_capture(
    capture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    capture = await _get_capture_or_404(db, user, capture_id)

    for att in capture.attachments:
        try:
            delete_capture_file(att.storage_path)
        except Exception:
            pass

    await db.delete(capture)
    await db.flush()


@router.post("/{capture_id}/archive", response_model=CaptureResponse)
async def archive_capture(
    capture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    capture = await _get_capture_or_404(db, user, capture_id)
    capture.status = CaptureStatus.archived
    await db.flush()
    await db.refresh(capture)
    return _response(capture)


@router.post("/{capture_id}/review", response_model=CaptureResponse)
async def review_capture(
    capture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    capture = await _get_capture_or_404(db, user, capture_id)
    capture.status = CaptureStatus.reviewed
    await db.flush()
    await db.refresh(capture)
    return _response(capture)


@router.post("/{capture_id}/attachments", response_model=CaptureResponse)
async def add_attachment(
    capture_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    capture = await _get_capture_or_404(db, user, capture_id)

    mime = file.content_type or ""
    if mime in ALLOWED_IMAGE_MIMES:
        kind = "image"
        max_bytes = MAX_IMAGE_BYTES
    elif mime in ALLOWED_AUDIO_MIMES:
        kind = "audio"
        max_bytes = MAX_AUDIO_BYTES
    else:
        raise HTTPException(status_code=422, detail=f"Unsupported file type: {mime}")

    file_bytes = await file.read()
    if len(file_bytes) > max_bytes:
        limit_mb = max_bytes / (1024 * 1024)
        raise HTTPException(status_code=422, detail=f"File too large. Max {limit_mb:.0f}MB for {kind}")

    try:
        storage_path = upload_capture_file(user.id, file_bytes, file.filename or "upload", mime)
        import logging
        logging.getLogger(__name__).info(f"Uploaded attachment to {storage_path}")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail="Azure Storage is not configured. Please set AZURE_STORAGE_CONNECTION_STRING.")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to upload attachment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

    attachment = CaptureAttachment(
        capture_id=capture.id,
        user_id=user.id,
        kind=kind,
        file_name=file.filename or "upload",
        mime_type=mime,
        size_bytes=len(file_bytes),
        storage_path=storage_path,
    )
    db.add(attachment)

    if capture.capture_type == CaptureType.text:
        capture.capture_type = CaptureType(kind)
    elif capture.capture_type not in (CaptureType.mixed, CaptureType(kind)):
        capture.capture_type = CaptureType.mixed

    await db.flush()
    await db.refresh(capture)
    return _response(capture)


@router.delete("/{capture_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    capture_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    capture = await _get_capture_or_404(db, user, capture_id)

    attachment = None
    for att in capture.attachments:
        if att.id == attachment_id:
            attachment = att
            break

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    try:
        delete_capture_file(attachment.storage_path)
    except Exception:
        pass

    await db.delete(attachment)
    await db.flush()


@router.get("/{capture_id}/attachments/{attachment_id}/url", response_model=dict)
async def get_attachment_url(
    capture_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    capture = await _get_capture_or_404(db, user, capture_id)

    attachment = None
    for att in capture.attachments:
        if att.id == attachment_id:
            attachment = att
            break

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    try:
        url = get_blob_download_url(attachment.storage_path)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail="Azure Storage is not configured. Please set AZURE_STORAGE_CONNECTION_STRING.")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Attachment file not found in storage")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {str(e)}")
    
    return {"url": url, "mime_type": attachment.mime_type, "file_name": attachment.file_name}
