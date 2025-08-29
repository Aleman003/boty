from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any
from services.agent import infer_json
from services.memory import load_slots, merge_slots, recent_dialog

router = APIRouter()

class InferReq(BaseModel):
    wa_id: str
    text: str
    slots: Dict[str, Any] | None = None
    dialog: List[str] | None = None

@router.post("/infer")
async def infer(r: InferReq):
    slots = r.slots or load_slots(r.wa_id)
    dialog = r.dialog or recent_dialog(r.wa_id, limit=10)
    out = await infer_json(r.wa_id, r.text, slots, dialog)
    if out.slots:
        merge_slots(r.wa_id, out.slots)
    return out.model_dump()
