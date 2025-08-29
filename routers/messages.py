from fastapi import APIRouter
from pydantic import BaseModel
from services.whatsapp import send_text

router = APIRouter()

class SendReq(BaseModel):
    to: str
    body: str

@router.post("/send")
async def send(r: SendReq):
    await send_text(r.to, r.body)
    return {"ok": True}
