import os, re, httpx
from tenacity import retry, wait_exponential, stop_after_attempt
from core.config import settings

GRAPH = settings.GRAPH_VER
PHONE_ID = settings.WHATSAPP_PHONE_ID
TOKEN = settings.WHATSAPP_TOKEN

def normalize_mx(num: str) -> str:
    s = re.sub(r"\D", "", num or "")
    if s.startswith("00"): s = s[2:]
    if s.startswith("521") and len(s) == 13: s = "52" + s[3:]
    if len(s) == 10: s = "52" + s
    return s

@retry(wait=wait_exponential(min=1, max=8), stop=stop_after_attempt(3))
async def send_text(to: str, body: str):
    url = f"https://graph.facebook.com/{GRAPH}/{PHONE_ID}/messages"
    payload = {"messaging_product":"whatsapp",
               "to": normalize_mx(to),
               "type":"text",
               "text":{"body": (body or "")[:4096]}}
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()

async def mark_as_read(wamid: str):
    url = f"https://graph.facebook.com/{GRAPH}/{PHONE_ID}/messages"
    payload = {"messaging_product":"whatsapp","status":"read","message_id": wamid}
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
