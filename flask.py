from flask import Flask, request, jsonify
import os, requests

ACCESS_TOKEN = os.getenv("WHATSAPP_TOKEN")  # tu token
PHONE_NUMBER_ID = os.getenv("757333040793710")  # ej. 1234567890
MY_WA_ID = os.getenv("528128793882")  # tu número en formato internacional sin +
# opcional: para deduplicar
seen_ids = set()

app = Flask(__name__)

@app.get("/webhook")
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    # valida tu verify_token
    if mode == "subscribe" and token == os.getenv("WA_VERIFY_TOKEN"):
        print("Webhook verificado ✅")
        return challenge, 200
    return "forbidden", 403

@app.post("/webhook")
def receive():
    data = request.get_json(silent=True) or {}
    try:
        print("DEBUG BODY:", data)

        entries = data.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {}) or {}

                # ---- Logs de diagnóstico ----
                if "messages" in value:
                    print(">>> 📩 LLEGÓ messages")
                if "statuses" in value:
                    print(">>> ✅ LLEGÓ statuses (entregado/leer)")

                # 0) Ignora exclusivamente statuses
                if value.get("statuses"):
                    continue

                # 1) Procesa mensajes entrantes
                messages = value.get("messages", [])
                if not messages:
                    continue

                msg = messages[0]
                msg_id = msg.get("id")
                from_wa = msg.get("from")  # ej: '52181...'
                msg_type = msg.get("type")

                # 1.1) Anti-duplicados
                if msg_id and msg_id in seen_ids:
                    print(f"SKIP duplicado: {msg_id}")
                    continue
                if msg_id:
                    seen_ids.add(msg_id)

                # 1.2) No te respondas a ti mismo
                if MY_WA_ID and from_wa and from_wa.endswith(MY_WA_ID):
                    print("SKIP mensaje propio (MY_WA_ID).")
                    continue

                # 1.3) Extraer texto según tipo
                text_in = ""
                if msg_type == "text":
                    text_in = (msg.get("text", {}).get("body") or "").strip()
                elif msg_type == "interactive":
                    ir = msg.get("interactive", {}) or {}
                    if ir.get("type") == "button_reply":
                        text_in = (ir.get("button_reply", {}).get("id") or "").strip()
                    elif ir.get("type") == "list_reply":
                        text_in = (ir.get("list_reply", {}).get("id") or "").strip()
                elif msg_type == "image":
                    text_in = "(imagen recibida)"
                elif msg_type == "audio":
                    text_in = "(audio recibido)"
                else:
                    text_in = f"(mensaje tipo {msg_type})"

                print(f"FROM: {from_wa} | TYPE: {msg_type} | TEXT: {text_in}")

                # 2) Respuesta sencilla (puedes cambiar por tu IA)
                reply = _respuesta_basica(text_in)

                # 3) Enviar respuesta
                if from_wa and reply:
                    send_text(from_wa, reply)
                    print(">> Enviado OK")
                else:
                    print("WARN: Falta from_wa o reply vacío.")

        # WhatsApp exige 200 siempre
        return "ok", 200

    except Exception as e:
        # Nunca devolver error distinto de 200 para que no reintenten infinito
        print("ERROR webhook:", repr(e))
        return "ok", 200


def _respuesta_basica(texto: str) -> str:
    """Reglas mínimas de conversación (placeholder). Cambia por tu IA."""
    t = (texto or "").lower()

    if any(w in t for w in ["hola", "buen día", "buen dia", "hi"]):
        return ("¡Claro, a tus órdenes! 🙌\n"
                "¿Qué visa necesitas?\n"
                "• B1/B2 (turismo/negocios)\n"
                "• Trabajo (chofer / empleada doméstica)\n"
                "• Cita de emergencia\n"
                "Dime cuál te interesa y para cuántas personas.")

    if "visa" in t and "emergencia" in t:
        return ("Ok perfecto. Para **cita de emergencia** necesito saber:\n"
                "1) Motivo de emergencia\n"
                "2) Ciudad para entrevista\n"
                "3) ¿Para cuántas personas?\n"
                "Te voy guiando paso a paso 🙂")

    if "trabajo" in t or "chofer" in t or "empleada" in t:
        return ("Entendido. Para **visa de trabajo**:\n"
                "• ¿De qué empresa proviene la oferta?\n"
                "• ¿Puesto y ciudad?\n"
                "• ¿Para cuántas personas es el trámite?")

    if "b1" in t or "b2" in t or "turis" in t or "negocio" in t:
        return ("Perfecto. Para **visa B1/B2**:\n"
                "• ¿Cuántas personas aplican?\n"
                "• ¿Ciudad para la entrevista?\n"
                "• ¿Alguna vez han tenido visa o les han negado?")

    # fallback
    return ("Te leo 👌. Cuéntame brevemente qué necesitas para orientarte mejor.\n"
            "Puedo apoyar con B1/B2, trabajo (chofer/empleada doméstica) y cita de emergencia.")


def send_text(to_wa, text):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_wa,
        "type": "text",
        "text": {"body": text}
    }
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    r = requests.post(url, json=payload, headers=headers, timeout=15)
    if r.status_code >= 300:
        print("Fallo al enviar:", r.status_code, r.text)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
