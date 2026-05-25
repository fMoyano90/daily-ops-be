from __future__ import annotations

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import async_session
from app.services.jira_sync import sync_all_enabled

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


async def _run_jira_sync_job() -> None:
    logger.info("Ejecutando sync programado de Jira")
    try:
        async with async_session() as session:
            try:
                results = await sync_all_enabled(session)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        for r in results:
            logger.info(
                "Jira sync %s: status=%s created=%d updated=%d errors=%d",
                r.connection_name, r.status, r.created, r.updated, len(r.errors),
            )
    except Exception:
        logger.exception("Fallo en job de sync de Jira")


def start_scheduler() -> Optional[AsyncIOScheduler]:
    global _scheduler
    if not settings.JIRA_SYNC_ENABLED:
        logger.info("Scheduler de Jira deshabilitado (JIRA_SYNC_ENABLED=false)")
        return None
    if _scheduler is not None:
        return _scheduler

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_jira_sync_job,
        trigger="interval",
        minutes=settings.JIRA_SYNC_INTERVAL_MINUTES,
        id="jira_sync_all",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("Scheduler de Jira arrancado (cada %s min)", settings.JIRA_SYNC_INTERVAL_MINUTES)
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
