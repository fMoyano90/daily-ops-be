"""Web push notification service.

Uses pywebpush to deliver VAPID-signed push messages to subscribed endpoints.
Subscriptions that respond 404/410 are pruned from the database.
"""
from __future__ import annotations

import json
import logging
from uuid import UUID

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)


def _vapid_claims() -> dict:
    email = settings.VAPID_CONTACT_EMAIL or "admin@dailyops.local"
    return {"sub": f"mailto:{email}"}


async def send_to_user(
    db: AsyncSession,
    user_id: UUID,
    *,
    title: str,
    body: str,
    url: str = "/today",
    icon: str | None = None,
) -> int:
    """Send a push notification to every active subscription for `user_id`.

    Returns the number of subscriptions successfully reached.
    """
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
        logger.warning("VAPID keys not configured; skipping push send")
        return 0

    result = await db.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    )
    subs = result.scalars().all()
    if not subs:
        return 0

    payload = json.dumps({"title": title, "body": body, "url": url, "icon": icon})
    sent = 0
    stale_ids: list[UUID] = []

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims=_vapid_claims(),
            )
            sent += 1
        except WebPushException as exc:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
            if status in (404, 410):
                stale_ids.append(sub.id)
            else:
                logger.warning("Push failed for sub %s: %s", sub.id, exc)
        except Exception:  # noqa: BLE001 - we want to keep iterating
            logger.exception("Unexpected push send error for sub %s", sub.id)

    if stale_ids:
        await db.execute(delete(PushSubscription).where(PushSubscription.id.in_(stale_ids)))
        await db.commit()

    return sent


async def touch_subscription(db: AsyncSession, sub: PushSubscription) -> None:
    """Update last_seen_at; cheap heartbeat from the frontend."""
    from datetime import datetime, timezone

    await db.execute(
        update(PushSubscription)
        .where(PushSubscription.id == sub.id)
        .values(last_seen_at=datetime.now(timezone.utc))
    )
    await db.commit()
