from __future__ import annotations

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import async_session
from app.services.jira_sync import sync_all_enabled
from app.services.day_closer import auto_close_previous_days

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


async def _run_auto_close_day_job() -> None:
    logger.info("Ejecutando cierre automático de días pendientes")
    try:
        async with async_session() as session:
            try:
                results = await auto_close_previous_days(session)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        if results:
            for r in results:
                logger.info(
                    "Auto-cierre día %s: user=%s plan_id=%s completed=%d rolled_over=%d skipped=%d",
                    r["date"], r.get("user_email", "?"), r["plan_id"],
                    r["summary"]["completed"], r["summary"]["rolled_over"], r["summary"]["skipped"],
                )
        else:
            logger.info("No hay días pendientes para cerrar automáticamente")
    except Exception:
        logger.exception("Fallo en job de cierre automático de días")


def start_scheduler() -> Optional[AsyncIOScheduler]:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    scheduler = AsyncIOScheduler()
    
    if settings.JIRA_SYNC_ENABLED:
        scheduler.add_job(
            _run_jira_sync_job,
            trigger="interval",
            minutes=settings.JIRA_SYNC_INTERVAL_MINUTES,
            id="jira_sync_all",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        logger.info("Scheduler de Jira arrancado (cada %s min)", settings.JIRA_SYNC_INTERVAL_MINUTES)
    else:
        logger.info("Scheduler de Jira deshabilitado (JIRA_SYNC_ENABLED=false)")
    
    if settings.AUTO_CLOSE_ENABLED:
        scheduler.add_job(
            _run_auto_close_day_job,
            trigger="cron",
            hour=settings.AUTO_CLOSE_HOUR,
            minute=settings.AUTO_CLOSE_MINUTE,
            id="auto_close_day",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        logger.info(
            "Cierre automático configurado a las %02d:%02d",
            settings.AUTO_CLOSE_HOUR, settings.AUTO_CLOSE_MINUTE,
        )
    else:
        logger.info("Cierre automático deshabilitado (AUTO_CLOSE_ENABLED=false)")
    
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
