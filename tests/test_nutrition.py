import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.database import get_db
from app.dependencies import get_current_user
from app.main import app
from app.models.nutrition import ActivityLevel, HealthProfile, NutritionDay, NutritionDayStatus, NutritionGoal, Sex
from app.routers import nutrition as nutrition_router
from app.services.nutrition_ai import AnalyzedDay, ExerciseAnalysis, MealAnalysis


class FakeScalarResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeResult:
    def __init__(self, *, one=None, many=None):
        self.one = one
        self.many = many or []

    def scalar_one_or_none(self):
        return self.one

    def scalar_one(self):
        return self.one

    def scalars(self):
        return FakeScalarResult(self.many)


class FakeDb:
    def __init__(self, results):
        self.results = list(results)
        self.added = []
        self.deleted = []

    async def execute(self, _statement):
        if not self.results:
            raise AssertionError("Unexpected query")
        return self.results.pop(0)

    def add(self, instance):
        self.added.append(instance)

    async def delete(self, instance):
        self.deleted.append(instance)

    async def flush(self):
        return None

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


def make_profile(user_id):
    profile = HealthProfile(
        id=uuid.uuid4(),
        user_id=user_id,
        sex=Sex.male,
        birth_date=date(1990, 1, 1),
        height_cm=178,
        weight_kg=80,
        activity_level=ActivityLevel.moderate,
        goal=NutritionGoal.lose,
        glass_ml=200,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return profile


def make_day(user_id, log_date=date(2026, 5, 29)):
    return NutritionDay(
        id=uuid.uuid4(),
        user_id=user_id,
        date=log_date,
        water_ml=0,
        status=NutritionDayStatus.draft,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_nutrition_today_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/nutrition/today")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_nutrition_profile_upsert(client: AsyncClient, fake_user, override_auth):
    fake_db = FakeDb([FakeResult(one=None)])
    override_db(fake_db)

    response = await client.put(
        "/api/v1/nutrition/profile",
        json={
            "sex": "male",
            "birth_date": "1990-01-01",
            "height_cm": 178,
            "weight_kg": 80,
            "activity_level": "moderate",
            "goal": "lose",
            "glass_ml": 200,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(fake_user.id)
    assert data["bmr"] > 0
    assert data["tdee"] > data["bmr"]
    assert data["recommended_calories"] == data["tdee"] - 500


@pytest.mark.asyncio
async def test_nutrition_create_meal_and_exercise(client: AsyncClient, fake_user, override_auth):
    meal_db = FakeDb([FakeResult(one=None), FakeResult(one=None), FakeResult(one=0)])
    override_db(meal_db)
    meal_response = await client.post("/api/v1/nutrition/meals", json={"date": "2026-05-29", "description": "pan con jamon"})
    assert meal_response.status_code == 201
    assert meal_response.json()["label"] == "Comida 1"

    exercise_db = FakeDb([FakeResult(one=None), FakeResult(one=None), FakeResult(one=0)])
    override_db(exercise_db)
    exercise_response = await client.post(
        "/api/v1/nutrition/exercises",
        json={"date": "2026-05-29", "description": "trote lento 15 min"},
    )
    assert exercise_response.status_code == 201
    assert exercise_response.json()["label"] == "Ejercicio 1"


@pytest.mark.asyncio
async def test_nutrition_water_uses_profile_glass_size(client: AsyncClient, fake_user, override_auth):
    day = make_day(fake_user.id)
    profile = make_profile(fake_user.id)
    profile.glass_ml = 250
    fake_db = FakeDb([
        FakeResult(one=day),
        FakeResult(one=profile),
        FakeResult(many=[]),
        FakeResult(many=[]),
    ])
    override_db(fake_db)

    response = await client.post("/api/v1/nutrition/2026-05-29/water", json={"delta": 2})

    assert response.status_code == 200
    assert response.json()["water_ml"] == 500


@pytest.mark.asyncio
async def test_nutrition_analyze_writes_estimations(client: AsyncClient, fake_user, override_auth, monkeypatch):
    profile = make_profile(fake_user.id)
    day = make_day(fake_user.id)
    meal = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=fake_user.id,
        daily_plan_id=None,
        date=day.date,
        label="Comida 1",
        description="pan con jamon",
        sort_order=0,
        calories=None,
        protein_g=None,
        carbs_g=None,
        sugar_g=None,
        fat_g=None,
        fiber_g=None,
        ai_notes=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    exercise = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=fake_user.id,
        daily_plan_id=None,
        date=day.date,
        label="Ejercicio 1",
        description="trote lento 15 min",
        sort_order=0,
        calories_burned=None,
        duration_min=None,
        intensity=None,
        ai_notes=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_db = FakeDb([
        FakeResult(one=profile),
        FakeResult(many=[meal]),
        FakeResult(many=[exercise]),
        FakeResult(one=day),
        FakeResult(many=[meal]),
        FakeResult(many=[exercise]),
    ])
    override_db(fake_db)

    async def fake_analyze_day(_profile, _meals, _exercises):
        return AnalyzedDay(
            meals=[MealAnalysis(index=0, calories=350, protein_g=18, carbs_g=45, sugar_g=6, fat_g=12, fiber_g=3)],
            exercises=[ExerciseAnalysis(index=0, calories_burned=120, duration_min=15, intensity="low")],
            day_summary="Dia estimado correctamente.",
        )

    monkeypatch.setattr(nutrition_router.nutrition_ai, "analyze_day", fake_analyze_day)

    response = await client.post("/api/v1/nutrition/2026-05-29/analyze")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "analyzed"
    assert data["consumed_calories"] == 350
    assert data["burned_calories"] == 120
    assert data["total_protein_g"] == 18
    assert data["meals"][0]["calories"] == 350
    assert data["exercises"][0]["calories_burned"] == 120
