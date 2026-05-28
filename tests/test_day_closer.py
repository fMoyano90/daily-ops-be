import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_close_plan_requires_auth(client: AsyncClient):
    response = await client.post("/api/v1/daily-plans/00000000-0000-0000-0000-000000000001/close")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_reopen_plan_requires_auth(client: AsyncClient):
    response = await client.post("/api/v1/daily-plans/00000000-0000-0000-0000-000000000001/reopen")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_today_suggestions_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/daily-plans/today/suggestions")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_plan_requires_auth(client: AsyncClient):
    from datetime import date, timedelta
    future_date = date.today() + timedelta(days=1)
    response = await client.post("/api/v1/daily-plans", json={"date": future_date.isoformat()})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_add_task_to_plan_requires_auth(client: AsyncClient):
    response = await client.post(
        "/api/v1/daily-plans/00000000-0000-0000-0000-000000000001/tasks",
        json={"task_id": "00000000-0000-0000-0000-000000000002"},
    )
    assert response.status_code == 403
