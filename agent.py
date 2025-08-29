# agent.py
import os, json, time, re, requests
from typing import Any, Dict
from pydantic import BaseModel, Field, ValidationError
from storage import get_slots, merge_slots, log_message, recent_dialog

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

PRICING = ("MRV ≈ 185 USD por persona; honorarios desde $1,500 MXN; "
           "adelanto de cita opcional desde $5,000 MXN; con adelanto el apoyo "
           "de trámite baja a $1,000 MXN. Pueden variar según consulado y fecha.")
PROCESS = "DS-160 → pago MRV → citas CAS/Consulado → acompañamiento hasta la decisión."
DOCS    = "Pasaporte vigente, comprobante de ingresos/empleo o info de negocio, y plan tentativo de viaje."

class AgentOut(BaseModel):
    reply: str
    quick_replies: list[str] = Field(default_factory=list)
    slots: Dict[str, Any] = Field(default_factory=dict)
    followups: list[str] = Field(default_factory=list)
    ask_delay_seconds: int = 0
    escalate_to_human: bool = False

SYSTEM_PROMPT = f"""
Eres asesor de visas en México. Tono humano, cálido y claro.
Normas:
- Máximo 1 pregunta por turno. No repitas saludos si ya hubo uno.
- Usa el nombre si existe `slots.contact_name`, no en cada línea.
- No inventes datos. Costos/tiempos válidos: {PRICING}
- Proceso base: {PROCESS}
- Documentos base: {DOCS}
- Si aparece tema legal sensible (deportación, asilo, fraude, antecedentes): escalas a humano.

Responde SOLO JSON con claves: reply, quick_replies, slots, followups, ask_delay_seconds, escalate_to_human.
"""

FEW_SHOTS = [
    {"role":"user","content":"hola"},
    {"role":"assistant","content": json.dumps({
        "reply": "¡Hola! ¿Con quién tengo el gusto?",
        "quick_replies": [],
        "slots": {"stage":"ask_name"},
        "followups": [],
        "ask_delay_seconds": 0,
        "escalate_to_human": False
    }, ensure_ascii=False)},
]

def strip_redundant_saludo(text: str, greeted: bool) -> str:
    if greeted and re.match(r'^\s*(hola|buen[oa]s?)\b', text or "", re.I):
        parts = re.split(r'(?<=[.!?])\s+', text, maxsplit=1)
        if len(parts) == 2:
            return parts[1]
    return text

def grounded_or_caution(text: str) -> str:
    if not text: return text
    # si detecta números sospechosos, reemplaza por texto político
    if re.search(r"\$\s*\d{5,}", text) or re.search(r"\b\d{3,5}\s*usd\b", text, re.I):
        return ("Te comparto rangos autorizados: MRV ~185 USD pp; honorarios desde $1,500 MXN; "
                "adelanto desde $5,000 MXN. Pueden variar según consulado y fecha.")
    return text

def ai_reply(wa_id: str, user_text: str) -> AgentOut:
    fallback = AgentOut(
        reply="¿Te comparto costos, el proceso o la lista de documentos?",
        quick_replies=["Costos","Proceso","Documentos"]
    )
    slots = get_slots(wa_id)

    if not OPENAI_API_KEY:
        return fallback

    dialog = "\n".join(recent_dialog(wa_id, limit=10))
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *FEW_SHOTS,
        {"role": "system", "content": f"Slots actuales: {json.dumps(slots, ensure_ascii=False)}"},
        {"role": "system", "content": f"Historial reciente:\n{dialog}"},
        {"role": "user", "content": user_text or ""},
    ]
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0.4,
        "max_tokens": 450
    }
    t0 = time.time()
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type":"application/json"},
            json=payload, timeout=45
        )
        if resp.status_code != 200:
            return fallback
        content = resp.json()["choices"][0]["message"]["content"]
        raw = json.loads(content)
        out = AgentOut.model_validate(raw)

        greeted = slots.get("stage") not in (None, "new", "ask_name")
        out.reply = grounded_or_caution(strip_redundant_saludo(out.reply, greeted))

        if out.slots:
            merge_slots(wa_id, out.slots)

        return out
    except (ValidationError, Exception):
        return fallback
