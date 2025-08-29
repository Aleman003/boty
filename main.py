# C:\agent_lap\boty\main.py
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import PlainTextResponse, JSONResponse
import os, json, requests

# --- Cargar .env ---
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

client = OpenAI()  
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")

app = FastAPI(title="Visa Sales Agent API", version="1.0.0")

# --- ENV ---
WHATSAPP_TOKEN   = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID  = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN     = os.getenv("WHATSAPP_VERIFY_TOKEN")

print("DEBUG .env path:", BASE_DIR / ".env")
print("DEBUG PHONE_NUMBER_ID:", repr(PHONE_NUMBER_ID))
print("DEBUG VERIFY_TOKEN:",    repr(VERIFY_TOKEN))

# --- Utilidades ---
def normalize_for_send(wa_id: str) -> str:
    """
    MX móviles llegan como '521XXXXXXXXXX'. Si tu allowlist/Meta guarda sin el '1',
    convertimos '521' → '52' + 10 dígitos SOLO para enviar.
    """
    if wa_id and wa_id.startswith("521") and len(wa_id) == 13:
        return "52" + wa_id[3:]
    return wa_id

def pretty_number(wa_id: str) -> str:
    """Para logs legibles (p. ej. '+52 81 2879 3882')."""
    if not wa_id:
        return "+"
    digits = wa_id[-10:] if len(wa_id) >= 10 else wa_id
    return f"+52 {digits[:2]} {digits[2:6]} {digits[6:]}"

def whatsapp_send_text(to: str, body: str) -> dict:
    """Envío de texto con manejo de errores y warnings útiles."""
    if not PHONE_NUMBER_ID:
        return {"status": 0, "resp": "PHONE_NUMBER_ID vacío. Revisa tu .env"}
    if not WHATSAPP_TOKEN:
        return {"status": 0, "resp": "WHATSAPP_TOKEN vacío. Revisa tu .env"}

    url = f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,  # E.164 SIN '+'
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }

    print("DEBUG SEND URL:", url)
    print("DEBUG SEND PAYLOAD:", json.dumps(payload, ensure_ascii=False))

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        try:
            resp = r.json()
        except Exception:
            resp = {"raw_text": r.text}

        print("DEBUG SEND STATUS:", r.status_code)
        print("DEBUG SEND RESP:", json.dumps(resp, ensure_ascii=False))

        # --- Warnings útiles ---
        if isinstance(resp, dict) and "error" in resp:
            err = resp.get("error", {})
            code  = err.get("code")
            msg   = err.get("message", "")
            edata = err.get("error_data", {}) or {}

            # code 10 = permisos / app-token-PNID no coinciden
            if code == 10:
                print("⚠️  WARNING: code 10 (permissions). "
                      "Este token no tiene permiso para este PHONE_NUMBER_ID "
                      "o pertenece a otra app/WABA. Prueba con el Temporary token de API Setup "
                      "o asigna el System User a la WABA y regenera el permanent token con "
                      "`whatsapp_business_messaging` y `whatsapp_business_management`.")

            # 131030 = destinatario no permitido (allowlist con test number)
            if code == 131030:
                print("⚠️  WARNING: code 131030 (recipient not in allowed list). "
                      f"Verifica que el número '{to}' esté en API Setup → Add recipient phone number. "
                      "Si usas normalización MX, agrega el formato EXACTO que se envía.")

        return {"status": r.status_code, "resp": resp}

    except requests.RequestException as e:
        print("DEBUG SEND ERROR:", repr(e))
        return {"status": -1, "resp": str(e)}

# --- Rutas ---
@app.get("/", include_in_schema=False)
def root():
    return {"status": "ok", "docs": "/docs"}

# Verificación GET (Meta)
@app.get("/webhook", response_class=PlainTextResponse, summary="Verify")
def verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
):
    print("DEBUG params => mode:", hub_mode, " token:", hub_verify_token, " challenge:", hub_challenge)
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN and hub_challenge:
        return hub_challenge  # texto plano
    raise HTTPException(status_code=403, detail="verify failed")


CONVO = {}  # dict[str, list[dict]]

SELLER_SYSTEM_PROMPT = (
    "Eres un asesor de visas de Traviex. Tono: cálido, profesional y directo; "
    "español MX; tuteo; frases cortas; UNA sola pregunta por turno. "
    "Mulettillas permitidas: 'Buen día', 'Claro, a tus órdenes', 'Perfecto', "
    "'Listo', 'Ok perfecto', 'Me explico?', 'Quedo a sus órdenes', "
    "'Cualquier duda estoy al pendiente', 'Disculpa el interrogatorio jaja', "
    "'Permíteme para poder escucharlo'. "
    "Flujo: saluda → detecta interés → preguntas graduales (visa/relación; "
    "ubicación; empresa si trabajo; tiempo laborando; ingreso mensual; propiedades/vehículos; deudas; hijos; historial migratorio/visa previa; problemas legales*). "
    "Explica costos orientativos B1/B2: MRV aprox. 185 USD (sujeto a cambio), "
    "trámite base $1,500 MXN, 'adelanto de cita' $5,000 MXN y entonces trámite baja a $1,000 MXN; "
    "con adelanto, tiempos estimados ~4–6 meses. Cierra ofreciendo acompañamiento y seguimiento. "
    "Siempre una sola pregunta al final. Marca de cierre amable."
    "\n*Si detectas palabras de problema legal fuerte, responde profesional y neutro sin asesoría legal."
)

def ai_reply(from_wa: str, user_text: str) -> str:
    history = CONVO.get(from_wa, [])

    messages = [{"role":"system","content": SELLER_SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role":"user","content": user_text})

    try:
        resp = client.chat.completions.create(
            model=os.getenv("AI_MODEL", "gpt-4o-mini"),
            temperature=0.7,
            max_tokens=350,
            messages=messages,
        )
        answer = (resp.choices[0].message.content or "").strip()

        # Actualiza memoria (máx 10 turnos)
        history.extend([{"role":"user","content": user_text},
                        {"role":"assistant","content": answer}])
        CONVO[from_wa] = history[-10:]
        return answer or "Claro, a tus órdenes. ¿En qué te ayudo?"
    except Exception as e:
        print("ERROR OpenAI:", e)
        return ("Estoy disponible 🙂. ¿Qué visa te interesa (B1/B2, trabajo, cita de emergencia) "
                "y para cuántas personas?")
        
# Recepción POST (mensajes)
@app.post("/webhook", summary="Receive")
async def receive(req: Request):
    data = await req.json()
    print("DEBUG POST BODY:", json.dumps(data, ensure_ascii=False))

    try:
        entry    = (data.get("entry") or [{}])[0]
        changes  = (entry.get("changes") or [{}])[0]
        value    = changes.get("value") or {}
        messages = value.get("messages") or []

        # muchos eventos son 'statuses'; responde 200 para evitar reintentos
        if not messages:
            print("DEBUG: evento sin 'messages' (ignorando).")
            return JSONResponse({"status": "ignored"}, status_code=200)

        msg      = messages[0]
        from_raw = msg.get("from")                      # ej. 521812XXXXXX
        mtype    = msg.get("type")                      # 'text', 'button', etc.

        text_in = ""
        if mtype == "text":
            text_in = (msg.get("text") or {}).get("body") or ""
        elif mtype == "button":
            text_in = (msg.get("button") or {}).get("text") or "(button)"
        else:
            text_in = f"(tipo {mtype})"

        # Normalización y logs
        to_send   = normalize_for_send(from_raw)        # p.ej. 528128XXXXXX si venía 521...
        pretty    = pretty_number(from_raw)

        print("INCOMING => from_raw:", from_raw, "| pretty:", pretty, "| type:", mtype, "| text:", text_in)
        print("DEBUG to_send:", to_send)

        reply_text = "¡Webhook activo ✅! Ya puedo responder."
        send_res   = whatsapp_send_text(to_send, reply_text)

        return JSONResponse({"ok": True, "reply": send_res}, status_code=200)

    except Exception as e:
        print("ERROR receive:", repr(e))
        # Devuelve 200 para que Meta no reintente de forma agresiva
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)

# Debug local (bórralo en prod)
@app.get("/env-check", include_in_schema=False)
def env_check():
    return {
        "PHONE_NUMBER_ID": PHONE_NUMBER_ID,
        "HAS_TOKEN": bool(WHATSAPP_TOKEN),
        "VERIFY_TOKEN": VERIFY_TOKEN,
    }

# Arranque local
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=3000, reload=True)
