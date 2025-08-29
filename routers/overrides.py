from fastapi import APIRouter
from pydantic import BaseModel
from services.overrides import pending, submit_human

router = APIRouter()

@router.get("/pending")
def list_pending():
    return pending()

class OverrideReq(BaseModel):
    wa_id: str
    text: str

@router.post("/reply")
def reply(r: OverrideReq):
    ok = submit_human(r.wa_id, r.text)
    return {"ok": ok}
