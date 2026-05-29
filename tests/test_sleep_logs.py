import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_sleep_logs_today_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/sleep-logs/today")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sleep_logs_list_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/sleep-logs")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sleep_logs_create_requires_auth(client: AsyncClient):
    response = await client.post(
        "/api/v1/sleep-logs",
        json={"hours_slept": 7.5, "sleep_quality": 8},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sleep_logs_weekly_summary_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/sleep-logs/summary/week")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sleep_logs_monthly_summary_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/sleep-logs/summary/month")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sleep_logs_update_requires_auth(client: AsyncClient):
    response = await client.patch(
        "/api/v1/sleep-logs/00000000-0000-0000-0000-000000000001",
        json={"sleep_quality": 7},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sleep_logs_delete_requires_auth(client: AsyncClient):
    response = await client.delete("/api/v1/sleep-logs/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 403
