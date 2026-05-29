import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.database import get_db
from app.dependencies import get_current_user
from app.main import app
from app.models.health import ConditionCategory, ConditionStatus, EpisodeType, HealthCondition


class FakeScalarResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeResult:
    def __init__(self, *, one=None, many=None, rows=None):
        self.one = one
        self.many = many or []
        self.rows = rows or []

    def scalar_one_or_none(self):
        return self.one

    def scalar_one(self):
        return self.one

    def scalars(self):
        return FakeScalarResult(self.many)

    def all(self):
        return self.rows


class FakeDb:
    def __init__(self, results):
        self.results = list(results)
        self.added = []
        self.deleted = []

    async def execute(self, _statement):
        if not self.results:
            raise AssertionError("Unexpected query")
        result = self.results.pop(0)
        return result(self) if callable(result) else result

    def add(self, instance):
        self.added.append(instance)

    async def delete(self, instance):
        self.deleted.append(instance)

    async def flush(self):
        now = datetime.now(timezone.utc)
        for instance in self.added:
            if getattr(instance, "id", None) is None:
                instance.id = uuid.uuid4()
            if getattr(instance, "created_at", None) is None:
                instance.created_at = now
            if getattr(instance, "updated_at", None) is None:
                instance.updated_at = now

    async def refresh(self, instance):
        now = datetime.now(timezone.utc)
        if getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()
        if getattr(instance, "created_at", None) is None:
            instance.created_at = now
        if getattr(instance, "updated_at", None) is None:
            instance.updated_at = now


@pytest.fixture
def fake_user():
    return SimpleNamespace(id=uuid.uuid4(), is_active=True)


@pytest.fixture
def override_auth(fake_user):
    async def _current_user():
        return fake_user

    app.dependency_overrides[get_current_user] = _current_user
    yield
    app.dependency_overrides.clear()


def override_db(fake_db):
    async def _db():
        yield fake_db

    app.dependency_overrides[get_db] = _db


def make_condition(user_id):
    return HealthCondition(
        id=uuid.uuid4(),
        user_id=user_id,
        name="Hipertension",
        category=ConditionCategory.cardiovascular,
        status=ConditionStatus.active,
        description="Presion alta",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_health_conditions_require_auth(client: AsyncClient):
    response = await client.get("/api/v1/health/conditions")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_health_create_condition_guideline_episode_and_summary(client: AsyncClient, fake_user, override_auth):
    condition_db = FakeDb([lambda db: FakeResult(one=db.added[-1])])
    override_db(condition_db)

    condition_response = await client.post(
        "/api/v1/health/conditions",
        json={"name": "Hipertension", "category": "cardiovascular", "description": "Presion alta"},
    )

    assert condition_response.status_code == 201
    condition_data = condition_response.json()
    assert condition_data["user_id"] == str(fake_user.id)
    assert condition_data["guidelines"] == []

    condition = make_condition(fake_user.id)
    condition.id = uuid.UUID(condition_data["id"])
    guideline_db = FakeDb([FakeResult(one=condition), FakeResult(one=0)])
    override_db(guideline_db)

    guideline_response = await client.post(
        f"/api/v1/health/conditions/{condition.id}/guidelines",
        json={"kind": "avoid", "text": "Evitar exceso de sal"},
    )

    assert guideline_response.status_code == 201
    assert guideline_response.json()["text"] == "Evitar exceso de sal"

    episode_db = FakeDb([FakeResult(one=condition.id)])
    override_db(episode_db)

    episode_response = await client.post(
        "/api/v1/health/episodes",
        json={
            "condition_id": str(condition.id),
            "episode_type": "physical",
            "title": "Dolor de cabeza",
            "started_on": "2026-05-29",
            "severity": 3,
        },
    )

    assert episode_response.status_code == 201
    assert episode_response.json()["severity"] == 3

    summary_db = FakeDb([FakeResult(rows=[(EpisodeType.physical, 1)])])
    override_db(summary_db)

    summary_response = await client.get("/api/v1/health/episodes/summary?date_from=2026-05-01&date_to=2026-05-31")

    assert summary_response.status_code == 200
    assert summary_response.json()["total"] == 1
    assert summary_response.json()["by_type"] == {"physical": 1}
