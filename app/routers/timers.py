from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from uuid import UUID

from app.database import get_db
from app.dependencies import get_current_user
from app.models.daily_task import DailyTask, DailyTaskStatus
from app.models.timer_session import TimerSession
from app.models.user import User
from app.schemas.timer_session import TimerSessionResponse, TimerStartResponse, TimerStopResponse

router = APIRouter(prefix="/api/v1/daily-tasks/{task_id}/timer", tags=["timers"])


async def verify_task_ownership(db: AsyncSession, task_id: UUID, user: User):
    task = await db.get(DailyTask, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Daily task not found")
    return task


@router.post("/start", response_model=TimerStartResponse, status_code=status.HTTP_201_CREATED)
async def start_timer(task_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await verify_task_ownership(db, task_id, user)

    result = await db.execute(
        select(TimerSession)
        .where(TimerSession.daily_task_id == task_id, TimerSession.user_id == user.id)
        .where(TimerSession.stopped_at == None)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Timer already running for this task")

    if task.status == DailyTaskStatus.planned:
        task.status = DailyTaskStatus.in_progress
        task.started_at = datetime.now(timezone.utc)

    session = TimerSession(
        daily_task_id=task_id,
        user_id=user.id,
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    return {"session_id": session.id, "started_at": session.started_at}


@router.post("/pause", response_model=TimerSessionResponse)
async def pause_timer(task_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await verify_task_ownership(db, task_id, user)

    result = await db.execute(
        select(TimerSession)
        .where(TimerSession.daily_task_id == task_id, TimerSession.user_id == user.id)
        .where(TimerSession.stopped_at == None)
        .order_by(TimerSession.started_at.desc())
    )
    active_session = result.scalar_one_or_none()
    if not active_session:
        raise HTTPException(status_code=400, detail="No active timer session")

    active_session.stopped_at = datetime.now(timezone.utc)
    delta = active_session.stopped_at - active_session.started_at
    active_session.duration_seconds = int(delta.total_seconds())

    total_result = await db.execute(
        select(func.sum(TimerSession.duration_seconds))
        .where(TimerSession.daily_task_id == task_id, TimerSession.user_id == user.id)
    )
    total_seconds = total_result.scalar() or 0
    task.total_seconds = total_seconds

    task.status = DailyTaskStatus.paused
    await db.flush()
    await db.refresh(active_session)
    return active_session


@router.post("/resume", response_model=TimerStartResponse, status_code=status.HTTP_201_CREATED)
async def resume_timer(task_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await verify_task_ownership(db, task_id, user)

    result = await db.execute(
        select(TimerSession)
        .where(TimerSession.daily_task_id == task_id, TimerSession.user_id == user.id)
        .where(TimerSession.stopped_at == None)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Timer already running for this task")

    task.status = DailyTaskStatus.in_progress

    session = TimerSession(
        daily_task_id=task_id,
        user_id=user.id,
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    return {"session_id": session.id, "started_at": session.started_at}


@router.post("/stop", response_model=TimerStopResponse)
async def stop_timer(task_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await verify_task_ownership(db, task_id, user)

    result = await db.execute(
        select(TimerSession)
        .where(TimerSession.daily_task_id == task_id, TimerSession.user_id == user.id)
        .where(TimerSession.stopped_at == None)
        .order_by(TimerSession.started_at.desc())
    )
    active_session = result.scalar_one_or_none()
    if not active_session:
        raise HTTPException(status_code=400, detail="No active timer session")

    active_session.stopped_at = datetime.now(timezone.utc)
    delta = active_session.stopped_at - active_session.started_at
    active_session.duration_seconds = int(delta.total_seconds())

    total_result = await db.execute(
        select(func.sum(TimerSession.duration_seconds))
        .where(TimerSession.daily_task_id == task_id, TimerSession.user_id == user.id)
    )
    total_seconds = total_result.scalar() or 0
    task.total_seconds = total_seconds

    await db.flush()
    await db.refresh(active_session)

    return {
        "session_id": active_session.id,
        "stopped_at": active_session.stopped_at,
        "duration_seconds": active_session.duration_seconds,
        "task_total_seconds": task.total_seconds,
    }


@router.post("/reset")
async def reset_timer(task_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await verify_task_ownership(db, task_id, user)

    await db.execute(delete(TimerSession).where(TimerSession.daily_task_id == task_id, TimerSession.user_id == user.id))
    task.total_seconds = 0
    task.status = DailyTaskStatus.planned
    task.started_at = None
    await db.flush()

    return {"task_total_seconds": 0, "status": task.status.value}


@router.get("/sessions", response_model=list[TimerSessionResponse])
async def get_timer_sessions(task_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = await verify_task_ownership(db, task_id, user)
    result = await db.execute(
        select(TimerSession)
        .where(TimerSession.daily_task_id == task_id, TimerSession.user_id == user.id)
        .order_by(TimerSession.started_at.desc())
    )
    return result.scalars().all()
