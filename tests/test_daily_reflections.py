import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_daily_reflections_today_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/daily-reflections/today")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_daily_reflections_list_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/daily-reflections")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_daily_reflections_weekly_summary_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/daily-reflections/summary/week")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_daily_reflections_monthly_summary_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/daily-reflections/summary/month")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_daily_reflections_update_requires_auth(client: AsyncClient):
    response = await client.patch(
        "/api/v1/daily-reflections/00000000-0000-0000-0000-000000000001",
        json={"went_well": "good day"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_daily_reflections_delete_requires_auth(client: AsyncClient):
    response = await client.delete("/api/v1/daily-reflections/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 403
