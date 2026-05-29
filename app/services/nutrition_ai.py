from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from app.config import settings


@dataclass
class MealAnalysis:
    index: int
    calories: int
    protein_g: float
    carbs_g: float
    sugar_g: float
    fat_g: float
    fiber_g: float
    notes: str | None = None


@dataclass
class ExerciseAnalysis:
    index: int
    calories_burned: int
    duration_min: int | None = None
    intensity: str | None = None
    notes: str | None = None


@dataclass
class AnalyzedDay:
    meals: list[MealAnalysis]
    exercises: list[ExerciseAnalysis]
    day_summary: str


def _number(value: Any, default: float = 0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    return default


async def analyze_day(profile: Any, meals: list[Any], exercises: list[Any]) -> AnalyzedDay:
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured")

    try:
        from anthropic import APIError, AsyncAnthropic
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Anthropic SDK is not installed") from exc

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=settings.ANTHROPIC_TIMEOUT_SECONDS)
    tool = {
        "name": "submit_analysis",
        "description": "Return one structured nutrition analysis for the full day.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meals": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "calories": {"type": "integer", "minimum": 0},
                            "protein_g": {"type": "number", "minimum": 0},
                            "carbs_g": {"type": "number", "minimum": 0},
                            "sugar_g": {"type": "number", "minimum": 0},
                            "fat_g": {"type": "number", "minimum": 0},
                            "fiber_g": {"type": "number", "minimum": 0},
                            "notes": {"type": "string"},
                        },
                        "required": ["index", "calories", "protein_g", "carbs_g", "sugar_g", "fat_g", "fiber_g"],
                    },
                },
                "exercises": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "calories_burned": {"type": "integer", "minimum": 0},
                            "duration_min": {"type": "integer", "minimum": 0},
                            "intensity": {"type": "string", "enum": ["low", "moderate", "high", "unknown"]},
                            "notes": {"type": "string"},
                        },
                        "required": ["index", "calories_burned"],
                    },
                },
                "day_summary": {"type": "string"},
            },
            "required": ["meals", "exercises", "day_summary"],
        },
    }
    payload = {
        "profile": {
            "sex": profile.sex.value if hasattr(profile.sex, "value") else profile.sex,
            "birth_date": profile.birth_date.isoformat(),
            "height_cm": profile.height_cm,
            "weight_kg": profile.weight_kg,
            "activity_level": profile.activity_level.value if hasattr(profile.activity_level, "value") else profile.activity_level,
            "goal": profile.goal.value if hasattr(profile.goal, "value") else profile.goal,
        },
        "meals": [{"index": idx, "label": meal.label, "description": meal.description} for idx, meal in enumerate(meals)],
        "exercises": [
            {"index": idx, "label": exercise.label, "description": exercise.description}
            for idx, exercise in enumerate(exercises)
        ],
    }

    try:
        message = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=2000,
            system=[
                {
                    "type": "text",
                    "text": (
                        "Eres un nutricionista deportivo. Estima kcal y macros de comidas en texto libre, "
                        "y kcal quemadas por ejercicios usando el perfil corporal disponible. Devuelve valores "
                        "razonables y conservadores. Devuelve comidas y ejercicios con los mismos indices "
                        "0-based recibidos en el input, sin omitir ni duplicar indices. No des coaching "
                        "conversacional; solo llama la herramienta."
                    ),
                    "cache_control": {"type": "ephemeral", "ttl": "5m"},
                }
            ],
            messages=[{"role": "user", "content": f"Analiza este dia completo:\n{payload}"}],
            tools=[tool],
            tool_choice={"type": "tool", "name": "submit_analysis"},
        )
    except APIError as exc:
        raise HTTPException(status_code=502, detail=f"Claude nutrition analysis failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Claude nutrition analysis failed") from exc

    tool_input = None
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "submit_analysis":
            tool_input = getattr(block, "input", None)
            break
    if not isinstance(tool_input, dict):
        raise HTTPException(status_code=502, detail="Claude did not return structured nutrition analysis")

    try:
        analyzed_meals = [
            MealAnalysis(
                index=int(item.get("index", -1)),
                calories=max(int(_number(item.get("calories"))), 0),
                protein_g=max(_number(item.get("protein_g")), 0),
                carbs_g=max(_number(item.get("carbs_g")), 0),
                sugar_g=max(_number(item.get("sugar_g")), 0),
                fat_g=max(_number(item.get("fat_g")), 0),
                fiber_g=max(_number(item.get("fiber_g")), 0),
                notes=item.get("notes") if isinstance(item.get("notes"), str) else None,
            )
            for item in tool_input.get("meals", [])
            if isinstance(item, dict)
        ]
        analyzed_exercises = [
            ExerciseAnalysis(
                index=int(item.get("index", -1)),
                calories_burned=max(int(_number(item.get("calories_burned"))), 0),
                duration_min=int(_number(item.get("duration_min"))) if item.get("duration_min") is not None else None,
                intensity=item.get("intensity") if isinstance(item.get("intensity"), str) else None,
                notes=item.get("notes") if isinstance(item.get("notes"), str) else None,
            )
            for item in tool_input.get("exercises", [])
            if isinstance(item, dict)
        ]
        summary = tool_input.get("day_summary")
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Claude returned malformed nutrition values") from exc

    return AnalyzedDay(
        meals=analyzed_meals,
        exercises=analyzed_exercises,
        day_summary=summary if isinstance(summary, str) else "Analisis generado sin resumen textual.",
    )
