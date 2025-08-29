# whatsapp.py
import os, json, re, httpx, time
from typing import Tuple
from tenacity import retry, wait_exponential, stop_after_attempt

GRAPH_VER = os.getenv("GRAPH_VER", "v20.0")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")

def normalize_mx(msisdn: str) -> str:
    s = re.sub(r"\D", "", msisdn or "")
    if s.startswith("00"): s = s[2:]
    if s.startswith("521") and len(s) == 13:
        s = "52" + s[3:]
    if len(s) == 10:
        s = "52" + s
    return s

@retry(wait=wait_exponential(min=1, max=8), stop=stop_after_attempt(3))
def _post(url: str, payload: dict) -> httpx.Response:
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    with httpx.Client(timeout=20) as client:
        r = client.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            raise RuntimeError(f"{r.status_code} {r.text[:300]}")
        return r

def send_text(to: str, body: str) -> Tuple[bool, str]:
    to_norm = normalize_mx(to)
    url = f"https://graph.facebook.com/{GRAPH_VER}/{WHATSAPP_PHONE_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_norm,
        "type": "text",
        "text": {"body": (body or "")[:4096]},
    }
    try:
        r = _post(url, payload)
        return True, r.text
    except Exception as e:
        txt = str(e)
        # Clasifica errores comunes
        if "190" in txt or "TOKEN_EXPIRED" in txt or "401" in txt:
            return False, "TOKEN_EXPIRED"
        if "131030" in txt:
            return False, "RECIPIENT_NOT_ALLOWED"
        if "Unsupported post request" in txt:
            return False, "BAD_ENDPOINT"
        return False, txt

def mark_as_read(wamid: str) -> Tuple[bool, str]:
    url = f"https://graph.facebook.com/{GRAPH_VER}/{WHATSAPP_PHONE_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": wamid
    }
    try:
        r = _post(url, payload)
        return True, r.text
    except Exception as e:
        return False, str(e)
