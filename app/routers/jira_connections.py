from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.jira_connection import DEFAULT_JIRA_JQL, JiraConnection
from app.models.project import Project, ProjectType
from app.models.task import Task, TaskSource
from app.models.user import User
from app.schemas.jira_connection import (
    JiraConnectionCreate,
    JiraConnectionResponse,
    JiraConnectionUpdate,
    JiraTestResponse,
    SyncResultResponse,
)
from app.services.crypto import encrypt_token, decrypt_token
from app.services.jira_client import JiraApiError, JiraAuthError, JiraClient
from app.services.jira_sync import sync_connection

router = APIRouter(prefix="/api/v1/jira-connections", tags=["jira"])


def _to_response(conn: JiraConnection) -> JiraConnectionResponse:
    return JiraConnectionResponse.model_validate(conn)


@router.get("", response_model=list[JiraConnectionResponse])
async def list_connections(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(JiraConnection).where(JiraConnection.user_id == user.id).order_by(JiraConnection.created_at))
    return [_to_response(c) for c in result.scalars().all()]


@router.post("", response_model=JiraConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(data: JiraConnectionCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    project = Project(
        name=f"Jira: {data.name}",
        type=ProjectType.work,
        color=data.project_color or "#2563eb",
        is_active=True,
        user_id=user.id,
    )
    db.add(project)
    await db.flush()

    conn = JiraConnection(
        name=data.name,
        base_url=str(data.base_url).rstrip("/"),
        email=data.email,
        api_token_encrypted=encrypt_token(data.api_token),
        jql=data.jql or DEFAULT_JIRA_JQL,
        project_id=project.id,
        enabled=True,
        user_id=user.id,
    )
    db.add(conn)
    await db.flush()
    await db.refresh(conn)
    return _to_response(conn)


@router.get("/{connection_id}", response_model=JiraConnectionResponse)
async def get_connection(connection_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    conn = await db.get(JiraConnection, connection_id)
    if not conn or conn.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conexión no encontrada")
    return _to_response(conn)


@router.patch("/{connection_id}", response_model=JiraConnectionResponse)
async def update_connection(
    connection_id: UUID,
    data: JiraConnectionUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conn = await db.get(JiraConnection, connection_id)
    if not conn or conn.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conexión no encontrada")

    updates = data.model_dump(exclude_unset=True)
    if "api_token" in updates:
        token = updates.pop("api_token")
        if token:
            conn.api_token_encrypted = encrypt_token(token)

    for key, value in updates.items():
        setattr(conn, key, value)

    await db.flush()
    await db.refresh(conn)
    return _to_response(conn)


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: UUID,
    purge_tasks: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conn = await db.get(JiraConnection, connection_id)
    if not conn or conn.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conexión no encontrada")

    project_id = conn.project_id

    if purge_tasks:
        await db.execute(
            delete(Task).where(
                Task.project_id == project_id,
                Task.source == TaskSource.jira,
                Task.user_id == user.id,
            )
        )

    await db.delete(conn)
    await db.flush()


@router.post("/{connection_id}/test", response_model=JiraTestResponse)
async def test_connection(connection_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    conn = await db.get(JiraConnection, connection_id)
    if not conn or conn.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conexión no encontrada")

    try:
        token = decrypt_token(conn.api_token_encrypted)
        async with JiraClient(conn.base_url, conn.email, token) as client:
            me = await client.whoami()
        return JiraTestResponse(
            ok=True,
            account_id=me.get("accountId"),
            display_name=me.get("displayName"),
            email=me.get("emailAddress"),
        )
    except (JiraAuthError, JiraApiError) as exc:
        return JiraTestResponse(ok=False, error=str(exc))
    except Exception as exc:
        return JiraTestResponse(ok=False, error=f"Error inesperado: {exc}")


@router.post("/{connection_id}/sync", response_model=SyncResultResponse)
async def sync_one(connection_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    conn = await db.get(JiraConnection, connection_id)
    if not conn or conn.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conexión no encontrada")
    result = await sync_connection(db, conn)
    return SyncResultResponse(**result.__dict__)
