# app.py
import os, re, json, time, hmac, hashlib, random
from typing import Any, Dict
from collections import OrderedDict
from flask import Flask, request, abort
from dotenv import load_dotenv

from storage import init_db, get_slots, merge_slots, log_message
from whatsapp import send_text, mark_as_read, normalize_mx
from agent import ai_reply
from validators import EMAIL_RX, GREET_ONLY_RX, NAME_HINT_RX, extract_email, extract_mx_phone
from human_override import request_human_reply, submit_human_reply, pending_requests
from monitoring import webhook_requests, wa_send_ok, wa_send_error, llm_latency
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

load_dotenv()
PORT = int(os.getenv("PORT", "3000"))
VERIFY_SIGNATURE = bool(int(os.getenv("VERIFY_SIGNATURE", "0")))
APP_SECRET = os.getenv("APP_SECRET", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "mi_verify_2025")

app = Flask(__name__)
init_db()

def log(*a): print(time.strftime("[%H:%M:%S]"), *a, flush=True)

class LRUSet:
    def __init__(self, cap=5000):
        self.cap = cap
        self.d = OrderedDict()
    def add_if_new(self, key: str) -> bool:
        if not key: return True
        if key in self.d:
            self.d.move_to_end(key)
            return False
        self.d[key] = None
        if len(self.d) > self.cap:
            self.d.popitem(last=False)
        return True

DEDUP = LRUSet(5000)

@app.get("/")
def root(): return "OK", 200

@app.get("/healthz")
def healthz(): return "ok", 200

@app.get("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

@app.get("/admin/pending")
def admin_pending():
    return pending_requests(), 200

@app.post("/admin/reply")
def admin_reply():
    data = request.get_json(silent=True) or {}
    wa_id = data.get("wa_id")
    text  = data.get("text")
    ok = submit_human_reply(wa_id, text or "")
    return ({"ok": True} if ok else {"ok": False, "error": "no pending/expired"}), 200

def verify_sig(req) -> bool:
    if not VERIFY_SIGNATURE: return True
    sig = req.headers.get("X-Hub-Signature-256", "")
    if not (APP_SECRET and sig.startswith("sha256=")): return False
    digest = hmac.new(APP_SECRET.encode(), req.data, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={digest}", sig)

def extract_text(msg: Dict[str, Any]):
    mtype = msg.get("type")
    option_id = None
    text = None
    if mtype == "text":
        text = (msg.get("text") or {}).get("body")
    elif mtype == "interactive":
        inter = msg.get("interactive") or {}
        btn = (inter.get("button_reply") or {})
        lst = (inter.get("list_reply") or {})
        text = btn.get("title") or lst.get("title") or btn.get("id") or lst.get("id")
        option_id = btn.get("id") or lst.get("id")
    return text, mtype, option_id

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    webhook_requests.inc()
    log(">> /webhook", request.method)

    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
            log("GET verify OK"); return challenge, 200
        log("GET verify FAILED"); return "verify failed", 403

    if not verify_sig(request):
        log("bad signature"); return abort(403)

    data = request.get_json(silent=True) or {}
    log("Body:", json.dumps(data, ensure_ascii=False)[:600])

    if data.get("object") != "whatsapp_business_account":
        return "ok", 200

    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            statuses = value.get("statuses", [])

            for st in statuses:
                log("Status:", st.get("status"), "id=", st.get("id"), "to=", st.get("recipient_id"))

            for msg in messages:
                wamid = msg.get("id")
                if wamid and not DEDUP.add_if_new(wamid):
                    log("dup-skip", wamid)
                    continue

                wa_id = msg.get("from")
                slots = get_slots(wa_id)

                # Capturar nombre del profile una sola vez
                if not slots.get("contact_name"):
                    profile = ((value.get("contacts") or [{}])[0].get("profile") or {})
                    pname = profile.get("name")
                    if pname:
                        toks = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", pname)
                        if toks:
                            merge_slots(wa_id, {"contact_name": toks[0].capitalize()})

                text, mtype, option_id = extract_text(msg)
                log("Tipo:", mtype, "| Texto:", repr(text))
                if not text:
                    if mtype == "audio":
                        send_text(wa_id, "Recibí tu audio 🙌 dame un momento para escucharlo.")
                    elif mtype in ("image", "document", "video"):
                        send_text(wa_id, "Recibí el archivo 👍 ¿Seguimos con requisitos o te paso costos?")
                    continue

                log_message(wa_id, "user", text)

                # Extrae email/phone si vinieron
                to_merge = {}
                em = extract_email(text)
                ph = extract_mx_phone(text)
                if em: to_merge["contact_email"] = em
                if ph: to_merge["contact_phone"] = ph
                if to_merge: merge_slots(wa_id, to_merge)

                tlow = text.lower()

                # Nombre declarado (“soy…/me llamo…”)
                if not slots.get("contact_name"):
                    m = re.search(r"\b(me llamo|mi nombre es|soy)\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)", text, re.I)
                    if m:
                        name = m.group(2).strip().split()[0].capitalize()
                        merge_slots(wa_id, {"contact_name": name, "stage":"ask_need"})
                        send_text(wa_id, f"Mucho gusto, {name}. Cuéntame brevemente qué necesitas (renovar, primera vez o dudas).")
                        log_message(wa_id, "assistant", f"Mucho gusto, {name}...")
                        continue

                # Saludo puro sin nombre → pedir nombre una vez
                if GREET_ONLY_RX.match(tlow) and not slots.get("contact_name"):
                    merge_slots(wa_id, {"stage":"ask_name"})
                    send_text(wa_id, "Hola 🙂 ¿Con quién tengo el gusto?")
                    log_message(wa_id, "assistant", "Hola 🙂 ¿Con quién tengo el gusto?")
                    continue

                # ---- IA principal ----
                user_for_llm = option_id or text
                t0 = time.time()
                out = ai_reply(wa_id, user_for_llm)
                llm_latency.observe(time.time() - t0)

                # typing human-like
                delay = min(max(out.ask_delay_seconds, 0), 2)
                if delay: time.sleep(delay)
                time.sleep(random.uniform(0.4, 1.0))

                # envía respuesta
                ok, info = send_text(wa_id, out.reply or "Listo ✅")
                if ok: wa_send_ok.inc()
                else: wa_send_error.labels(info).inc()
                log("WA send:", ok, info)
                log_message(wa_id, "assistant", out.reply or "Listo ✅")

                # followup corto
                if out.followups:
                    time.sleep(0.6)
                    send_text(wa_id, out.followups[0])
                    log_message(wa_id, "assistant", out.followups[0])

                # escalar a humano
                if out.escalate_to_human:
                    merge_slots(wa_id, {"stage":"escalado"})
                    send_text(wa_id, "Gracias por la info 🙏 Lo reviso con mi supervisor y te escribo en breve.")
                    # abre ventana de override (5 min)
                    human = request_human_reply(wa_id, ttl_seconds=300)
                    if human:
                        send_text(wa_id, human)
                        log_message(wa_id, "assistant", human)

                # marca leído
                if wamid:
                    mark_as_read(wamid)

    return "ok", 200

if __name__ == "__main__":
    log(f"Bot en puerto {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=True)
