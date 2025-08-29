import re
from typing import Optional

PRICING_TEXT = ("MRV ~185 USD por persona; honorarios desde $1,500 MXN; "
                "adelanto opcional desde $5,000 MXN (sujeto a cambios).")
PROCESS_TEXT = "DS-160 → pago MRV → citas CAS/Consulado → acompañamiento hasta la decisión."
DOCS_TEXT    = "Pasaporte vigente, comprobante de ingresos/empleo o info de negocio, plan tentativo de viaje."

INTENTS = [
    ("costos", re.compile(r"\b(costo|cu[aá]nto|precio|tarifa|honorarios|cobra[n]?)\b", re.I)),
    ("proceso", re.compile(r"\b(proceso|paso|flujo|cita[s]?|ds-?160|mrv)\b", re.I)),
    ("docs",    re.compile(r"\b(docu|papel|requisito[s]?)\b", re.I)),
    ("renov",   re.compile(r"\b(renov|venci[oó]|sin entrevista|iw)\b", re.I)),
]

def quick_intent_router(wa_id: str, text: str) -> Optional[str]:
    """Respuestas deterministas rápidas. Devuelve None si no matchea."""
    for label, rx in INTENTS:
        if rx.search(text or ""):
            if label == "costos":
                return f"{PRICING_TEXT}\n¿Para cuántas personas sería?"
            if label == "proceso":
                return f"{PROCESS_TEXT}\n¿Ya cuentan con pasaportes?"
            if label == "docs":
                return f"{DOCS_TEXT}\n¿Quieres que te mande un checklist breve?"
            if label == "renov":
                return "Si tu visa venció hace ≤48 meses podrías aplicar a 'sin entrevista'. ¿Cuándo venció la última?"
    return None

def grounding(text: str) -> str:
    """Evita números inventados; si detecta montos “raros” reemplaza por política."""
    import re as _r
    if _r.search(r"\$\s*\d{5,}", text) or _r.search(r"\b\d{3,5}\s*usd\b", text, _r.I):
        return PRICING_TEXT
    return text
