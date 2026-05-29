from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.health import EpisodeType, HealthCondition, HealthGuideline, HealthReminder, SicknessEpisode
from app.models.user import User
from app.schemas.health import (
    GuidelineSuggestionRequest,
    GuidelineSuggestionResponse,
    HealthConditionCreate,
    HealthConditionResponse,
    HealthConditionUpdate,
    HealthGuidelineCreate,
    HealthGuidelineResponse,
    HealthGuidelineUpdate,
    HealthReminderCreate,
    HealthReminderResponse,
    HealthReminderUpdate,
    SicknessEpisodeCreate,
    SicknessEpisodeResponse,
    SicknessEpisodeSummaryResponse,
    SicknessEpisodeUpdate,
)
from app.services import health_ai
from app.utils.timezone import local_today

router = APIRouter(prefix="/api/v1/health", tags=["health"])


async def _get_condition_or_404(db: AsyncSession, user: User, condition_id: UUID) -> HealthCondition:
    result = await db.execute(
        select(HealthCondition)
        .where(HealthCondition.id == condition_id, HealthCondition.user_id == user.id)
        .options(selectinload(HealthCondition.guidelines), selectinload(HealthCondition.reminders))
    )
    condition = result.scalar_one_or_none()
    if not condition:
        raise HTTPException(status_code=404, detail="Health condition not found")
    return condition


async def _get_guideline_or_404(db: AsyncSession, user: User, guideline_id: UUID) -> HealthGuideline:
    result = await db.execute(
        select(HealthGuideline)
        .join(HealthCondition)
        .where(HealthGuideline.id == guideline_id, HealthCondition.user_id == user.id)
    )
    guideline = result.scalar_one_or_none()
    if not guideline:
        raise HTTPException(status_code=404, detail="Health guideline not found")
    return guideline


async def _get_reminder_or_404(db: AsyncSession, user: User, reminder_id: UUID) -> HealthReminder:
    result = await db.execute(
        select(HealthReminder)
        .join(HealthCondition)
        .where(HealthReminder.id == reminder_id, HealthCondition.user_id == user.id)
    )
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Health reminder not found")
    return reminder


async def _get_episode_or_404(db: AsyncSession, user: User, episode_id: UUID) -> SicknessEpisode:
    result = await db.execute(select(SicknessEpisode).where(SicknessEpisode.id == episode_id, SicknessEpisode.user_id == user.id))
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Sickness episode not found")
    return episode


async def _validate_condition_id(db: AsyncSession, user: User, condition_id: UUID | None) -> None:
    if condition_id is None:
        return
    result = await db.execute(select(HealthCondition.id).where(HealthCondition.id == condition_id, HealthCondition.user_id == user.id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Health condition not found")


def _strip_payload(payload: dict) -> dict:
    return {key: value.strip() if isinstance(value, str) else value for key, value in payload.items()}


@router.get("/conditions", response_model=list[HealthConditionResponse])
async def list_conditions(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(HealthCondition)
        .where(HealthCondition.user_id == user.id)
        .options(selectinload(HealthCondition.guidelines), selectinload(HealthCondition.reminders))
        .order_by(HealthCondition.created_at.desc())
    )
    return result.scalars().all()


@router.post("/conditions", response_model=HealthConditionResponse, status_code=status.HTTP_201_CREATED)
async def create_condition(
    data: HealthConditionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    condition = HealthCondition(user_id=user.id, **_strip_payload(data.model_dump()))
    db.add(condition)
    await db.flush()
    return await _get_condition_or_404(db, user, condition.id)


@router.post("/conditions/suggest", response_model=GuidelineSuggestionResponse)
async def suggest_condition_guidelines(
    data: GuidelineSuggestionRequest,
    user: User = Depends(get_current_user),
):
    del user
    suggestions = await health_ai.suggest_guidelines(data.name.strip(), data.category.value if data.category else None)
    return GuidelineSuggestionResponse(
        avoid=suggestions.avoid,
        helps=suggestions.helps,
        action_plan=suggestions.action_plan,
    )


@router.get("/conditions/{condition_id}", response_model=HealthConditionResponse)
async def get_condition(
    condition_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _get_condition_or_404(db, user, condition_id)


@router.patch("/conditions/{condition_id}", response_model=HealthConditionResponse)
async def update_condition(
    condition_id: UUID,
    data: HealthConditionUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    condition = await _get_condition_or_404(db, user, condition_id)
    payload = _strip_payload(data.model_dump(exclude_unset=True))
    for key, value in payload.items():
        setattr(condition, key, value)
    await db.flush()
    return await _get_condition_or_404(db, user, condition.id)


@router.delete("/conditions/{condition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_condition(
    condition_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    condition = await _get_condition_or_404(db, user, condition_id)
    await db.delete(condition)
    await db.flush()


@router.post("/conditions/{condition_id}/guidelines", response_model=HealthGuidelineResponse, status_code=status.HTTP_201_CREATED)
async def create_guideline(
    condition_id: UUID,
    data: HealthGuidelineCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_condition_or_404(db, user, condition_id)
    payload = _strip_payload(data.model_dump())
    if "sort_order" not in data.model_fields_set:
        count_result = await db.execute(select(func.count(HealthGuideline.id)).where(HealthGuideline.condition_id == condition_id))
        payload["sort_order"] = int(count_result.scalar_one() or 0)
    guideline = HealthGuideline(condition_id=condition_id, **payload)
    db.add(guideline)
    await db.flush()
    await db.refresh(guideline)
    return guideline


@router.patch("/guidelines/{guideline_id}", response_model=HealthGuidelineResponse)
async def update_guideline(
    guideline_id: UUID,
    data: HealthGuidelineUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    guideline = await _get_guideline_or_404(db, user, guideline_id)
    payload = _strip_payload(data.model_dump(exclude_unset=True))
    for key, value in payload.items():
        setattr(guideline, key, value)
    await db.flush()
    await db.refresh(guideline)
    return guideline


@router.delete("/guidelines/{guideline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_guideline(
    guideline_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    guideline = await _get_guideline_or_404(db, user, guideline_id)
    await db.delete(guideline)
    await db.flush()


@router.post("/conditions/{condition_id}/reminders", response_model=HealthReminderResponse, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    condition_id: UUID,
    data: HealthReminderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_condition_or_404(db, user, condition_id)
    payload = _strip_payload(data.model_dump())
    if "sort_order" not in data.model_fields_set:
        count_result = await db.execute(select(func.count(HealthReminder.id)).where(HealthReminder.condition_id == condition_id))
        payload["sort_order"] = int(count_result.scalar_one() or 0)
    reminder = HealthReminder(condition_id=condition_id, **payload)
    db.add(reminder)
    await db.flush()
    await db.refresh(reminder)
    return reminder


@router.patch("/reminders/{reminder_id}", response_model=HealthReminderResponse)
async def update_reminder(
    reminder_id: UUID,
    data: HealthReminderUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    reminder = await _get_reminder_or_404(db, user, reminder_id)
    payload = _strip_payload(data.model_dump(exclude_unset=True))
    for key, value in payload.items():
        setattr(reminder, key, value)
    await db.flush()
    await db.refresh(reminder)
    return reminder


@router.delete("/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reminder(
    reminder_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    reminder = await _get_reminder_or_404(db, user, reminder_id)
    await db.delete(reminder)
    await db.flush()


@router.get("/episodes", response_model=list[SicknessEpisodeResponse])
async def list_episodes(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    episode_type: EpisodeType | None = Query(None),
    limit: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(SicknessEpisode).where(SicknessEpisode.user_id == user.id)
    if date_from:
        query = query.where(SicknessEpisode.started_on >= date_from)
    if date_to:
        query = query.where(SicknessEpisode.started_on <= date_to)
    if episode_type:
        query = query.where(SicknessEpisode.episode_type == episode_type)
    result = await db.execute(query.order_by(SicknessEpisode.started_on.desc(), SicknessEpisode.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.post("/episodes", response_model=SicknessEpisodeResponse, status_code=status.HTTP_201_CREATED)
async def create_episode(
    data: SicknessEpisodeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _validate_condition_id(db, user, data.condition_id)
    episode = SicknessEpisode(user_id=user.id, **_strip_payload(data.model_dump()))
    db.add(episode)
    await db.flush()
    await db.refresh(episode)
    return episode


@router.get("/episodes/summary", response_model=SicknessEpisodeSummaryResponse)
async def episodes_summary(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = local_today()
    start_date = date_from or today - timedelta(days=29)
    end_date = date_to or today
    result = await db.execute(
        select(SicknessEpisode.episode_type, func.count(SicknessEpisode.id))
        .where(SicknessEpisode.user_id == user.id, SicknessEpisode.started_on >= start_date, SicknessEpisode.started_on <= end_date)
        .group_by(SicknessEpisode.episode_type)
    )
    by_type = {episode_type.value if hasattr(episode_type, "value") else str(episode_type): int(count) for episode_type, count in result.all()}
    return SicknessEpisodeSummaryResponse(
        period_start=start_date,
        period_end=end_date,
        total=sum(by_type.values()),
        by_type=by_type,
    )


@router.get("/episodes/{episode_id}", response_model=SicknessEpisodeResponse)
async def get_episode(
    episode_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _get_episode_or_404(db, user, episode_id)


@router.patch("/episodes/{episode_id}", response_model=SicknessEpisodeResponse)
async def update_episode(
    episode_id: UUID,
    data: SicknessEpisodeUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    episode = await _get_episode_or_404(db, user, episode_id)
    payload = _strip_payload(data.model_dump(exclude_unset=True))
    if "condition_id" in payload:
        await _validate_condition_id(db, user, payload["condition_id"])
    for key, value in payload.items():
        setattr(episode, key, value)
    await db.flush()
    await db.refresh(episode)
    return episode


@router.delete("/episodes/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_episode(
    episode_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    episode = await _get_episode_or_404(db, user, episode_id)
    await db.delete(episode)
    await db.flush()
