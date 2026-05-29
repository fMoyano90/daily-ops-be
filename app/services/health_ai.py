from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from app.config import settings


@dataclass
class SuggestedGuidelines:
    avoid: list[str]
    helps: list[str]
    action_plan: list[str]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


async def suggest_guidelines(name: str, category: str | None) -> SuggestedGuidelines:
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured")

    try:
        from anthropic import APIError, AsyncAnthropic
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Anthropic SDK is not installed") from exc

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=settings.ANTHROPIC_TIMEOUT_SECONDS)
    tool = {
        "name": "submit_health_guidelines",
        "description": "Return structured general health self-care guidance for one condition.",
        "input_schema": {
            "type": "object",
            "properties": {
                "avoid": {"type": "array", "items": {"type": "string"}},
                "helps": {"type": "array", "items": {"type": "string"}},
                "action_plan": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["avoid", "helps", "action_plan"],
        },
    }
    payload = {"name": name, "category": category}

    try:
        message = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=1600,
            system=[
                {
                    "type": "text",
                    "text": (
                        "Eres un orientador de salud general. Sugiere recomendaciones prudentes en espanol para una "
                        "condicion declarada por el usuario: que evitar, que puede ayudar y un plan de accion simple. "
                        "Incluye siempre una indicacion breve de consultar a un medico/profesional de salud cuando "
                        "corresponda y deja claro que esto no reemplaza atencion medica. No diagnostiques, no indiques "
                        "dosis de medicamentos y no des coaching conversacional; solo llama la herramienta."
                    ),
                    "cache_control": {"type": "ephemeral", "ttl": "5m"},
                }
            ],
            messages=[{"role": "user", "content": f"Sugiere cuidados para esta condicion:\n{payload}"}],
            tools=[tool],
            tool_choice={"type": "tool", "name": "submit_health_guidelines"},
        )
    except APIError as exc:
        raise HTTPException(status_code=502, detail=f"Claude health suggestion failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Claude health suggestion failed") from exc

    tool_input = None
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "submit_health_guidelines":
            tool_input = getattr(block, "input", None)
            break
    if not isinstance(tool_input, dict):
        raise HTTPException(status_code=502, detail="Claude did not return structured health suggestions")

    suggestions = SuggestedGuidelines(
        avoid=_string_list(tool_input.get("avoid")),
        helps=_string_list(tool_input.get("helps")),
        action_plan=_string_list(tool_input.get("action_plan")),
    )
    if not suggestions.avoid and not suggestions.helps and not suggestions.action_plan:
        raise HTTPException(status_code=502, detail="Claude returned empty health suggestions")
    return suggestions
