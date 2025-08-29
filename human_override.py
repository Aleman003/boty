# human_override.py
import time, queue
from typing import Dict, Optional

_QUEUES: Dict[str, queue.Queue] = {}
_TTL: Dict[str, float] = {}

def request_human_reply(wa_id: str, ttl_seconds: int = 300) -> Optional[str]:
    q = _QUEUES.setdefault(wa_id, queue.Queue())
    _TTL[wa_id] = time.time() + ttl_seconds
    try:
        return q.get(timeout=ttl_seconds)
    except queue.Empty:
        _TTL.pop(wa_id, None)
        return None

def submit_human_reply(wa_id: str, text: str) -> bool:
    q = _QUEUES.get(wa_id)
    exp = _TTL.get(wa_id, 0)
    if not q or time.time() > exp:
        return False
    q.put(text)
    _TTL.pop(wa_id, None)
    return True

def pending_requests() -> Dict[str, int]:
    now = time.time()
    return {k: int(_TTL[k] - now) for k in list(_TTL.keys()) if _TTL[k] > now}
