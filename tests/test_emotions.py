import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_emotions_list_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/emotions")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_emotions_today_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/emotions/today")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_emotions_summary_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/emotions/summary/week")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_emotions_create_requires_auth(client: AsyncClient):
    response = await client.post(
        "/api/v1/emotions",
        json={
            "emotion": "alegria",
            "intensity": 5,
            "valence": "pleasant",
            "energy": "medium",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_emotions_delete_requires_auth(client: AsyncClient):
    response = await client.delete("/api/v1/emotions/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 403
