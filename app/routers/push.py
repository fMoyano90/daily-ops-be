from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.schemas.push_subscription import (
    PushSubscriptionCreate,
    PushSubscriptionResponse,
    PushSubscriptionList,
    PushTestRequest,
)
from app.services.push import send_to_user

router = APIRouter(prefix="/api/v1/push", tags=["push"])


@router.get("/vapid-public-key")
async def get_public_key():
    if not settings.VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=503, detail="Push not configured")
    return {"key": settings.VAPID_PUBLIC_KEY}


@router.post(
    "/subscribe",
    response_model=PushSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def subscribe(
    data: PushSubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = await db.execute(
        select(PushSubscription).where(
            PushSubscription.user_id == user.id,
            PushSubscription.endpoint == data.endpoint,
        )
    )
    sub = existing.scalar_one_or_none()
    if sub is None:
        sub = PushSubscription(
            user_id=user.id,
            endpoint=data.endpoint,
            p256dh=data.keys.p256dh,
            auth=data.keys.auth,
            user_agent=data.user_agent,
        )
        db.add(sub)
    else:
        sub.p256dh = data.keys.p256dh
        sub.auth = data.keys.auth
        sub.user_agent = data.user_agent
    await db.commit()
    await db.refresh(sub)
    return PushSubscriptionResponse.model_validate(sub)


@router.delete("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    endpoint: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await db.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user.id,
            PushSubscription.endpoint == endpoint,
        )
    )
    await db.commit()
    return None


@router.post("/test")
async def send_test(
    data: PushTestRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sent = await send_to_user(db, user.id, title=data.title, body=data.body, url=data.url)
    return {"sent": sent}


@router.get("/subscriptions", response_model=PushSubscriptionList)
async def list_subscriptions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PushSubscription)
        .where(PushSubscription.user_id == user.id)
        .order_by(PushSubscription.created_at.desc())
    )
    subs = result.scalars().all()
    return PushSubscriptionList(
        subscriptions=[PushSubscriptionListItem.model_validate(s) for s in subs],
        count=len(subs),
    )


@router.post("/keep-only-current", status_code=status.HTTP_204_NO_CONTENT)
async def keep_only_current(
    endpoint: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await db.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user.id,
            PushSubscription.endpoint != endpoint,
        )
    )
    await db.commit()
