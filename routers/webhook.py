from fastapi import APIRouter, Request, HTTPException
import hmac, hashlib, re, time
from core.config import settings
from services.dedupe import dedupe
from services.whatsapp import send_text, mark_as_read
from services.memory import load_slots, merge_slots, log_turn, recent_dialog
from services.policy import quick_intent_router, grounding
from services.agent import infer_json

router = APIRouter()

@router.get("/webhook")
async def verify(request: Request):
    q = dict(request.query_params)
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == settings.WHATSAPP_VERIFY_TOKEN:
        return q.get("hub.challenge")
    raise HTTPException(403, "verify failed")

def _verify_sig(req: Request, body: bytes) -> bool:
    if not settings.VERIFY_SIGNATURE:
        return True
    sig = req.headers.get("X-Hub-Signature-256", "")
    if not (settings.APP_SECRET and sig.startswith("sha256=")):
        return False
    digest = hmac.new(settings.APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={digest}", sig)

@router.post("/webhook")
async def receive(request: Request):
    body = await request.body()
    if not _verify_sig(request, body):
        raise HTTPException(403, "bad signature")

    data = await request.json()
    if data.get("object") != "whatsapp_business_account":
        return {"ok": True}

    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})

            for st in value.get("statuses", []):
                # opcional: log de delivered/read/failed
                pass

            for msg in value.get("messages", []):
                wamid = msg.get("id")
                if not dedupe.add_if_new(wamid):
                    continue

                wa_id = msg.get("from")
                text = None
                if msg.get("type") == "text":
                    text = (msg.get("text") or {}).get("body")
                elif msg.get("type") == "interactive":
                    inter = msg.get("interactive") or {}
                    btn = (inter.get("button_reply") or {})
                    lst = (inter.get("list_reply") or {})
                    text = btn.get("title") or lst.get("title") or btn.get("id") or lst.get("id")

                slots = load_slots(wa_id)

                # 1) toma nombre del perfil si no existe
                if not slots.get("contact_name"):
                    profile = ((value.get("contacts") or [{}])[0].get("profile") or {})
                    pname = profile.get("name")
                    if pname:
                        toks = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", pname)
                        if toks:
                            merge_slots(wa_id, {"contact_name": toks[0].capitalize()})

                # 2) sin texto → ack amable
                if not text:
                    await send_text(wa_id, "Recibí tu mensaje 🙌 ¿Quieres que te pase costos o requisitos?")
                    continue

                log_turn(wa_id, "user", text)

                # 3) router determinista
                routed = quick_intent_router(wa_id, text)
                if routed:
                    reply = grounding(routed)
                    await send_text(wa_id, reply)
                    log_turn(wa_id, "assistant", reply)
                    continue

                # 4) IA principal (JSON validado)
                dialog = recent_dialog(wa_id, limit=10)
                out = await infer_json(wa_id, text, slots, dialog)

                # 5) enviar y persistir
                await send_text(wa_id, out.reply or "Listo ✅")
                log_turn(wa_id, "assistant", out.reply or "Listo ✅")

                if out.followups:
                    await send_text(wa_id, out.followups[0])
                    log_turn(wa_id, "assistant", out.followups[0])

                if out.slots:
                    merge_slots(wa_id, out.slots)

                mid = msg.get("id")
                if mid:
                    await mark_as_read(mid)

    return {"ok": True}
