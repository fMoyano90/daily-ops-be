"""CLI script to sync all enabled Jira connections.

Run with: python -m app.scripts.sync_all_jira
Or schedule via cron/APScheduler.
"""
import asyncio
import logging

from app.database import AsyncSessionLocal
from app.services.jira_sync import sync_all_enabled

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Jira sync for all enabled connections")
    
    async with AsyncSessionLocal() as db:
        results = await sync_all_enabled(db)
    
    for r in results:
        logger.info(
            "Sync %s (%s): status=%s created=%d updated=%d skipped=%d errors=%d",
            r.connection_name,
            r.connection_id,
            r.status,
            r.created,
            r.updated,
            r.skipped,
            len(r.errors),
        )
        if r.errors:
            for err in r.errors:
                logger.error("  Error: %s", err)
    
    logger.info("Jira sync completed: %d connections processed", len(results))


if __name__ == "__main__":
    asyncio.run(main())
