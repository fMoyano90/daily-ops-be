import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["JIRA_ENCRYPTION_KEY"] = "test-encryption-key-32chars!!"
os.environ["FOUNDER_PASSWORD"] = "founderpass123"

from app.dependencies import create_access_token, get_password_hash
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def test_user_data():
    return {
        "email": "test@example.com",
        "display_name": "Test User",
        "password": "testpass123",
    }


@pytest.fixture
def auth_headers():
    user_id = str(uuid.uuid4())
    token = create_access_token({"sub": user_id})
    return {"Authorization": f"Bearer {token}", "_user_id": user_id}


@pytest.fixture
def founder_auth_headers():
    from app.config import settings
    user_id = str(uuid.uuid4())
    token = create_access_token({"sub": user_id, "email": settings.FOUNDER_EMAIL})
    return {"Authorization": f"Bearer {token}", "_user_id": user_id}
