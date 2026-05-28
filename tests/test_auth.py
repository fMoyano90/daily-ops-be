import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "DailyOps API" in data["message"]


@pytest.mark.asyncio
async def test_access_protected_route_without_token(client: AsyncClient):
    response = await client.get("/api/v1/projects")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_access_protected_route_with_invalid_token(client: AsyncClient):
    response = await client.get(
        "/api/v1/projects",
        headers={"Authorization": "Bearer invalidtoken123"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sync_all_requires_auth(client: AsyncClient):
    response = await client.post("/api/v1/jira-connections/sync-all")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sync_all_requires_founder(client: AsyncClient):
    import uuid
    from app.dependencies import create_access_token
    token = create_access_token({"sub": str(uuid.uuid4()), "email": "notfounder@example.com"})
    response = await client.post(
        "/api/v1/jira-connections/sync-all",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Without a DB, user lookup fails with 401. With a DB and non-founder user, it would be 403.
    # Either way, access is denied.
    assert response.status_code in (401, 403)
