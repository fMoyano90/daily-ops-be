import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_daily_tasks_requires_auth(client: AsyncClient):
    response = await client.patch("/api/v1/daily-tasks/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_daily_tasks_complete_requires_auth(client: AsyncClient):
    response = await client.post("/api/v1/daily-tasks/00000000-0000-0000-0000-000000000001/complete")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_daily_tasks_reorder_requires_auth(client: AsyncClient):
    response = await client.put("/api/v1/daily-tasks/00000000-0000-0000-0000-000000000001/tasks/order")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_daily_tasks_delete_requires_auth(client: AsyncClient):
    response = await client.delete("/api/v1/daily-tasks/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 403
