from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException

from app.config import settings


@dataclass
class SuggestedExercise:
    name: str
    exercise_type: str
    muscle_group: str | None = None
    sets: int | None = None
    reps: int | None = None
    weight_kg: float | None = None
    duration_min: int | None = None
    distance_km: float | None = None
    intensity: str | None = None
    notes: str | None = None
    rest_seconds_recommended: int | None = None


@dataclass
class CalorieEstimate:
    exercise_id: str
    calories: int


@dataclass
class CalorieResult:
    estimates: list[CalorieEstimate] = field(default_factory=list)
    total_calories: int = 0


def _number(value: Any, default: float = 0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    return default


def _get_client():
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured")
    try:
        from anthropic import APIError, AsyncAnthropic
        return AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=settings.ANTHROPIC_TIMEOUT_SECONDS), APIError
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Anthropic SDK is not installed") from exc


async def generate_routine(
    exercise_profile: Any,
    health_profile: Any | None,
    recent_days: list[Any],
    daily_context: dict | None = None,
) -> list[SuggestedExercise]:
    client, APIError = _get_client()

    tool = {
        "name": "submit_routine",
        "description": "Return a personalized workout routine for today.",
        "input_schema": {
            "type": "object",
            "properties": {
                "exercises": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "exercise_type": {"type": "string", "enum": ["strength", "cardio", "mobility", "recovery"]},
                            "muscle_group": {"type": "string"},
                            "sets": {"type": "integer", "minimum": 1},
                            "reps": {"type": "integer", "minimum": 1},
                            "weight_kg": {"type": "number", "minimum": 0},
                            "duration_min": {"type": "integer", "minimum": 1},
                            "distance_km": {"type": "number", "minimum": 0},
                            "intensity": {"type": "string", "enum": ["low", "moderate", "high"]},
                            "notes": {"type": "string"},
                            "rest_seconds_recommended": {"type": "integer", "minimum": 30, "maximum": 300},
                        },
                        "required": ["name", "exercise_type"],
                    },
                }
            },
            "required": ["exercises"],
        },
    }

    recent_history = []
    for day in recent_days:
        day_data: dict[str, Any] = {"date": str(day.date), "exercises": []}
        if hasattr(day, "_exercises"):
            for ex in day._exercises:
                day_data["exercises"].append({
                    "name": ex.name,
                    "type": ex.exercise_type.value if hasattr(ex.exercise_type, "value") else ex.exercise_type,
                    "muscle_group": ex.muscle_group,
                    "sets": ex.sets,
                    "reps": ex.reps,
                    "intensity": ex.intensity,
                    "duration_min": ex.duration_min,
                    "status": ex.status.value if hasattr(ex.status, "value") else ex.status,
                })
        day_data["rpe"] = day.rpe
        day_data["total_duration_min"] = day.total_duration_min
        recent_history.append(day_data)

    profile_data: dict[str, Any] = {}
    if exercise_profile:
        profile_data["available_days"] = exercise_profile.available_days
        profile_data["location"] = exercise_profile.location
        profile_data["equipment"] = exercise_profile.equipment
        profile_data["session_duration_min"] = exercise_profile.session_duration_min
        profile_data["fitness_level"] = exercise_profile.fitness_level
        profile_data["physical_restrictions"] = exercise_profile.physical_restrictions

    biometrics: dict[str, Any] = {}
    if health_profile:
        biometrics["weight_kg"] = health_profile.weight_kg
        biometrics["height_cm"] = health_profile.height_cm
        biometrics["goal"] = health_profile.goal.value if hasattr(health_profile.goal, "value") else health_profile.goal

    payload = {
        "profile": profile_data,
        "biometrics": biometrics,
        "recent_history": recent_history,
        "daily_context": daily_context or {},
    }

    try:
        message = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=2000,
            system=[
                {
                    "type": "text",
                    "text": (
                        "Eres un entrenador personal experto. Genera una rutina de entrenamiento personalizada para hoy "
                        "basándote en el perfil del usuario, su historial reciente y el contexto del día. "
                        "Respeta la recuperación muscular: no sobrecargues el mismo grupo muscular más de 2 días consecutivos. "
                        "Adapta la rutina al equipamiento disponible, lugar de entrenamiento y tiempo disponible. "
                        "Si el usuario reporta fatiga o sueño malo, reduce la intensidad. "
                        "Si tiene mucha energía, puedes aumentarla. "
                        "Solo llama la herramienta; no des respuestas conversacionales."
                    ),
                    "cache_control": {"type": "ephemeral", "ttl": "5m"},
                }
            ],
            messages=[{"role": "user", "content": f"Genera la rutina de hoy:\n{payload}"}],
            tools=[tool],
            tool_choice={"type": "tool", "name": "submit_routine"},
        )
    except APIError as exc:
        raise HTTPException(status_code=502, detail=f"Claude exercise routine generation failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Claude exercise routine generation failed") from exc

    tool_input = None
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "submit_routine":
            tool_input = getattr(block, "input", None)
            break
    if not isinstance(tool_input, dict):
        raise HTTPException(status_code=502, detail="Claude did not return a structured workout routine")

    try:
        return [
            SuggestedExercise(
                name=str(item.get("name", "Ejercicio")),
                exercise_type=item.get("exercise_type", "cardio"),
                muscle_group=item.get("muscle_group") if isinstance(item.get("muscle_group"), str) else None,
                sets=int(_number(item.get("sets"))) if item.get("sets") is not None else None,
                reps=int(_number(item.get("reps"))) if item.get("reps") is not None else None,
                weight_kg=_number(item.get("weight_kg")) if item.get("weight_kg") is not None else None,
                duration_min=int(_number(item.get("duration_min"))) if item.get("duration_min") is not None else None,
                distance_km=_number(item.get("distance_km")) if item.get("distance_km") is not None else None,
                intensity=item.get("intensity") if isinstance(item.get("intensity"), str) else None,
                notes=item.get("notes") if isinstance(item.get("notes"), str) else None,
                rest_seconds_recommended=int(_number(item.get("rest_seconds_recommended"))) if item.get("rest_seconds_recommended") is not None else None,
            )
            for item in tool_input.get("exercises", [])
            if isinstance(item, dict)
        ]
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Claude returned malformed exercise routine") from exc


async def calculate_calories(exercises: list[Any], weight_kg: float | None) -> CalorieResult:
    client, APIError = _get_client()

    tool = {
        "name": "submit_calorie_estimates",
        "description": "Return calorie estimates for each exercise.",
        "input_schema": {
            "type": "object",
            "properties": {
                "estimates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "exercise_id": {"type": "string"},
                            "calories": {"type": "integer", "minimum": 0},
                        },
                        "required": ["exercise_id", "calories"],
                    },
                },
                "total_calories": {"type": "integer", "minimum": 0},
            },
            "required": ["estimates", "total_calories"],
        },
    }

    payload = {
        "user_weight_kg": weight_kg,
        "exercises": [
            {
                "id": str(ex.id),
                "name": ex.name,
                "type": ex.exercise_type.value if hasattr(ex.exercise_type, "value") else ex.exercise_type,
                "sets": ex.sets,
                "reps": ex.reps,
                "weight_kg": ex.weight_kg,
                "duration_min": ex.duration_min,
                "distance_km": ex.distance_km,
                "intensity": ex.intensity,
            }
            for ex in exercises
        ],
    }

    try:
        message = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=1000,
            system=[
                {
                    "type": "text",
                    "text": (
                        "Eres un especialista en fisiología del ejercicio. Estima las calorías quemadas para cada ejercicio "
                        "basándote en el tipo, intensidad, duración, series, repeticiones, peso utilizado y el peso corporal. "
                        "Usa valores conservadores y realistas. Solo llama la herramienta."
                    ),
                    "cache_control": {"type": "ephemeral", "ttl": "5m"},
                }
            ],
            messages=[{"role": "user", "content": f"Calcula calorías quemadas:\n{payload}"}],
            tools=[tool],
            tool_choice={"type": "tool", "name": "submit_calorie_estimates"},
        )
    except APIError as exc:
        raise HTTPException(status_code=502, detail=f"Claude calorie calculation failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Claude calorie calculation failed") from exc

    tool_input = None
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "submit_calorie_estimates":
            tool_input = getattr(block, "input", None)
            break
    if not isinstance(tool_input, dict):
        raise HTTPException(status_code=502, detail="Claude did not return calorie estimates")

    try:
        estimates = [
            CalorieEstimate(
                exercise_id=str(item.get("exercise_id", "")),
                calories=max(int(_number(item.get("calories"))), 0),
            )
            for item in tool_input.get("estimates", [])
            if isinstance(item, dict)
        ]
        total = max(int(_number(tool_input.get("total_calories"))), 0)
        return CalorieResult(estimates=estimates, total_calories=total)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Claude returned malformed calorie estimates") from exc


async def generate_coach_message(current_day: Any, recent_days: list[Any]) -> str:
    client, APIError = _get_client()

    tool = {
        "name": "submit_coach_message",
        "description": "Return a short coaching message in Spanish.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
            },
            "required": ["message"],
        },
    }

    history = []
    for day in recent_days:
        history.append({
            "date": str(day.date),
            "total_calories_burned": day.total_calories_burned,
            "total_duration_min": day.total_duration_min,
            "rpe": day.rpe,
            "status": day.status.value if hasattr(day.status, "value") else day.status,
        })

    current = {
        "date": str(current_day.date),
        "total_calories_burned": current_day.total_calories_burned,
        "total_duration_min": current_day.total_duration_min,
        "rpe": current_day.rpe,
        "post_workout_state": current_day.post_workout_state,
    }

    payload = {"current_day": current, "recent_history": history}

    try:
        message = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=300,
            system=[
                {
                    "type": "text",
                    "text": (
                        "Eres un entrenador personal motivador. Analiza el historial de entrenamiento del usuario "
                        "y entrega un mensaje corto de coaching en español (máximo 2 oraciones). "
                        "Menciona patrones específicos: grupos musculares repetidos, rachas, fatiga acumulada, "
                        "consistencia o falta de ella. Sé específico, no genérico. Solo llama la herramienta."
                    ),
                    "cache_control": {"type": "ephemeral", "ttl": "5m"},
                }
            ],
            messages=[{"role": "user", "content": f"Genera mensaje de coaching:\n{payload}"}],
            tools=[tool],
            tool_choice={"type": "tool", "name": "submit_coach_message"},
        )
    except APIError as exc:
        raise HTTPException(status_code=502, detail=f"Claude coach message failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Claude coach message failed") from exc

    tool_input = None
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "submit_coach_message":
            tool_input = getattr(block, "input", None)
            break
    if not isinstance(tool_input, dict):
        raise HTTPException(status_code=502, detail="Claude did not return a coach message")

    msg = tool_input.get("message")
    return msg if isinstance(msg, str) else "Sigue adelante con tu entrenamiento."
