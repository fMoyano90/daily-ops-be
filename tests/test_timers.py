import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_timer_start_requires_auth(client: AsyncClient):
    response = await client.post("/api/v1/daily-tasks/00000000-0000-0000-0000-000000000001/timer/start")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_timer_pause_requires_auth(client: AsyncClient):
    response = await client.post("/api/v1/daily-tasks/00000000-0000-0000-0000-000000000001/timer/pause")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_timer_resume_requires_auth(client: AsyncClient):
    response = await client.post("/api/v1/daily-tasks/00000000-0000-0000-0000-000000000001/timer/resume")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_timer_stop_requires_auth(client: AsyncClient):
    response = await client.post("/api/v1/daily-tasks/00000000-0000-0000-0000-000000000001/timer/stop")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_timer_reset_requires_auth(client: AsyncClient):
    response = await client.post("/api/v1/daily-tasks/00000000-0000-0000-0000-000000000001/timer/reset")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_timer_sessions_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/daily-tasks/00000000-0000-0000-0000-000000000001/timer/sessions")
    assert response.status_code == 403
