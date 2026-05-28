from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jira_connection import JiraConnection
from app.models.task import Priority, Task, TaskSource, TaskStatus
from app.services.crypto import decrypt_token
from app.services.jira_client import JiraApiError, JiraAuthError, JiraClient, JiraIssue

logger = logging.getLogger(__name__)


JIRA_PRIORITY_MAP = {
    "highest": Priority.critical,
    "high": Priority.high,
    "medium": Priority.medium,
    "low": Priority.low,
    "lowest": Priority.low,
}


@dataclass
class SyncResult:
    connection_id: str
    connection_name: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    status: str = "ok"


def _map_priority(name: Optional[str]) -> Priority:
    if not name:
        return Priority.medium
    return JIRA_PRIORITY_MAP.get(name.strip().lower(), Priority.medium)


async def sync_connection(db: AsyncSession, conn: JiraConnection) -> SyncResult:
    result = SyncResult(connection_id=str(conn.id), connection_name=conn.name)

    try:
        token = decrypt_token(conn.api_token_encrypted)
    except Exception as exc:
        result.status = "error"
        result.errors.append(f"No se pudo desencriptar token: {exc}")
        conn.last_sync_at = datetime.now(timezone.utc)
        conn.last_sync_status = "error"
        conn.last_sync_error = result.errors[-1][:2000]
        await db.flush()
        return result

    try:
        async with JiraClient(conn.base_url, conn.email, token) as client:
            issues = await client.search_issues(conn.jql)
    except (JiraAuthError, JiraApiError) as exc:
        result.status = "error"
        result.errors.append(str(exc))
        conn.last_sync_at = datetime.now(timezone.utc)
        conn.last_sync_status = "error"
        conn.last_sync_error = str(exc)[:2000]
        await db.flush()
        return result
    except Exception as exc:
        result.status = "error"
        result.errors.append(f"Error inesperado: {exc}")
        conn.last_sync_at = datetime.now(timezone.utc)
        conn.last_sync_status = "error"
        conn.last_sync_error = str(exc)[:2000]
        await db.flush()
        logger.exception("Fallo inesperado sincronizando Jira %s", conn.name)
        return result

    for issue in issues:
        try:
            await _upsert_issue(db, conn, issue, result)
        except Exception as exc:
            result.errors.append(f"{issue.key}: {exc}")
            logger.exception("Error procesando issue %s", issue.key)

    conn.last_sync_at = datetime.now(timezone.utc)
    conn.last_sync_status = "ok" if not result.errors else "partial"
    conn.last_sync_error = "; ".join(result.errors)[:2000] if result.errors else None
    result.status = conn.last_sync_status
    await db.flush()
    return result


async def _upsert_issue(
    db: AsyncSession,
    conn: JiraConnection,
    issue: JiraIssue,
    result: SyncResult,
) -> None:
    stmt = select(Task).where(
        Task.source == TaskSource.jira,
        Task.external_url == issue.url,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    mapped_priority = _map_priority(issue.priority_name)

    if existing is None:
        task = Task(
            user_id=conn.user_id,
            project_id=conn.project_id,
            title=issue.summary or issue.key,
            description=issue.description_text,
            source=TaskSource.jira,
            external_key=issue.key,
            external_url=issue.url,
            status=TaskStatus.backlog,
            priority=mapped_priority,
            due_date=issue.due_date,
            category=issue.issue_type,
        )
        db.add(task)
        result.created += 1
        return

    existing.title = issue.summary or existing.title
    existing.description = issue.description_text
    existing.external_url = issue.url
    existing.priority = mapped_priority
    existing.due_date = issue.due_date
    if issue.issue_type:
        existing.category = issue.issue_type
    existing.updated_at = datetime.now(timezone.utc)
    result.updated += 1


async def sync_all_enabled(db: AsyncSession) -> list[SyncResult]:
    stmt = select(JiraConnection).where(JiraConnection.enabled == True)  # noqa: E712
    conns = (await db.execute(stmt)).scalars().all()

    results: list[SyncResult] = []
    for conn in conns:
        try:
            results.append(await sync_connection(db, conn))
        except Exception as exc:
            logger.exception("Fallo crítico sincronizando %s", conn.name)
            results.append(SyncResult(
                connection_id=str(conn.id),
                connection_name=conn.name,
                status="error",
                errors=[str(exc)],
            ))
    return results
