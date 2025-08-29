# services/ai_seller.py
from openai import OpenAI
from core.config import settings

client = OpenAI()  # usa OPENAI_API_KEY del .env
CONVO: dict[str, list[dict]] = {}       # memoria corta por número (10 turnos)

PROMPT = (
    "Eres un asesor de visas de Traviex. Tono cálido, profesional y directo (español MX, tuteo), "
    "frases cortas y UNA sola pregunta por turno. Muletillas: 'Buen día', 'Claro, a tus órdenes', "
    "'Perfecto', 'Listo', 'Ok perfecto', 'Me explico?', 'Quedo a sus órdenes', "
    "'Cualquier duda estoy al pendiente', 'Disculpa el interrogatorio jaja', "
    "'Permíteme para poder escucharlo'. Flujo de calificación: visa/relación; ubicación; "
    "si trabajan en la misma empresa; tiempo laborando; ingreso mensual; propiedades/vehículos; "
    "deudas; hijos; historial migratorio/visa previa; problemas legales. "
    "Para visa B1/B2: MRV ≈ 185 USD (sujeto a cambio), trámite base $1,500 MXN; "
    "con 'adelanto de cita' $5,000 MXN el trámite baja a $1,000 MXN; tiempos con adelanto ~4–6 meses. "
    "Siempre cierra ofreciendo acompañamiento y seguimiento, y deja una sola pregunta."
)

def ai_reply(user_id: str, text: str) -> str:
    hist = CONVO.get(user_id, [])
    msgs = [{"role": "system", "content": PROMPT}, *hist, {"role": "user", "content": text}]

    try:
        r = client.chat.completions.create(
            model=settings.AI_MODEL, temperature=0.7, max_tokens=350, messages=msgs
        )
        out = (r.choices[0].message.content or "").strip()
        hist.extend([{"role":"user","content":text},{"role":"assistant","content":out}])
        CONVO[user_id] = hist[-10:]
        return out or "Claro, a tus órdenes. ¿Qué visa te interesa y para cuántas personas?"
    except Exception as e:
        print("ERROR OpenAI:", e)
        return ("Estoy disponible 🙂. ¿Qué visa te interesa (B1/B2, trabajo, cita de emergencia) "
                "y para cuántas personas?")
