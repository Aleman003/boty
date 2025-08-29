from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
from services.memory import load_slots, merge_slots

router = APIRouter()

@router.get("/{wa_id}")
def get_slots(wa_id: str):
    return load_slots(wa_id)

class MergeReq(BaseModel):
    data: Dict[str, Any]

@router.put("/{wa_id}")
def put_slots(wa_id: str, r: MergeReq):
    return merge_slots(wa_id, r.data or {})
