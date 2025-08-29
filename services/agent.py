import os, json, time, httpx
from typing import Any, Dict, List
from pydantic import BaseModel, Field, ValidationError
from core.config import settings

class AgentOut(BaseModel):
    reply: str
    quick_replies: list[str] = Field(default_factory=list)
    slots: Dict[str, Any] = Field(default_factory=dict)
    followups: list[str] = Field(default_factory=list)
    ask_delay_seconds: int = 0
    escalate_to_human: bool = False

SYSTEM = """
Eres asesor de visas (MX). Tono cálido y claro. Máximo 1 pregunta por turno.
No inventes costos/plazos. Responde SOLO JSON: reply, quick_replies, slots, followups, ask_delay_seconds, escalate_to_human.
"""

async def infer_json(wa_id: str, user_text: str, slots: dict, dialog: list[str]) -> AgentOut:
    payload = {
      "model": settings.OPENAI_MODEL,
      "messages": [
        {"role":"system","content": SYSTEM},
        {"role":"system","content": f"Slots: {json.dumps(slots, ensure_ascii=False)}"},
        {"role":"system","content": "Historial:\n" + "\n".join(dialog)},
        {"role":"user","content": user_text or ""}
      ],
      "response_format": {"type": "json_object"},
      "temperature": 0.4,
      "max_tokens": 450
    }
    async with httpx.AsyncClient(timeout=40) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                     "Content-Type": "application/json"},
            json=payload
        )
    if r.status_code != 200:
        return AgentOut(reply="¿Te comparto costos, proceso o documentos?")
    try:
        content = r.json()["choices"][0]["message"]["content"]
        return AgentOut.model_validate(json.loads(content))
    except (KeyError, ValidationError, json.JSONDecodeError):
        return AgentOut(reply="¿Te comparto costos, proceso o documentos?")
