# storage.py
import os, json, sqlite3, time
from typing import Any, Dict, Tuple

DB_PATH = os.getenv("DB_PATH", "agent.db")

def _conn():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL;")
    return con

def init_db():
    con = _conn()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS slots (
      wa_id TEXT PRIMARY KEY,
      json  TEXT NOT NULL,
      updated_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      wa_id TEXT NOT NULL,
      role TEXT NOT NULL,      -- user|assistant|system
      text TEXT NOT NULL,
      ts   INTEGER NOT NULL
    );
    """)
    con.commit()
    con.close()

SLOT_TEMPLATE: Dict[str, Any] = {
    "contact_name": None,
    "stage": "new",  # new|ask_name|ask_need|dialog|cierre|escalado
    "visa_type": None,
    "purpose": "turismo",
    "persons_count": None,
    "employment_status": None,
    "monthly_income_mxn": None,
    "assets": None,
    "debts": None,
    "passports_ready": None,
    "travel_month": None,
    "stay_length_days": None,
    "previous_visa": None,
    "previous_visa_expiry": None,
    "legal_issues": None,
    "city": None,
    "contact_email": None,
    "contact_phone": None,
    "interested_in_renewal": None,
    "interested_in_expedite": None,
    "last_intent": None,
    "last_question": None,
    "last_answered_at": None
}

def get_slots(wa_id: str) -> Dict[str, Any]:
    con = _conn()
    cur = con.execute("SELECT json FROM slots WHERE wa_id=?", (wa_id,))
    row = cur.fetchone()
    con.close()
    if not row:
        return json.loads(json.dumps(SLOT_TEMPLATE))
    try:
        data = json.loads(row[0])
        for k, v in SLOT_TEMPLATE.items():
            data.setdefault(k, v)
        return data
    except Exception:
        return json.loads(json.dumps(SLOT_TEMPLATE))

def merge_slots(wa_id: str, new_slots: Dict[str, Any]) -> Dict[str, Any]:
    s = get_slots(wa_id)
    changed = False
    for k, v in (new_slots or {}).items():
        if v not in (None, "", [], {}) and k in s and s.get(k) != v:
            s[k] = v
            changed = True
    if changed:
        con = _conn()
        con.execute(
            "INSERT INTO slots(wa_id,json,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(wa_id) DO UPDATE SET json=excluded.json, updated_at=excluded.updated_at",
            (wa_id, json.dumps(s, ensure_ascii=False), int(time.time()))
        )
        con.commit()
        con.close()
    return s

def log_message(wa_id: str, role: str, text: str):
    con = _conn()
    con.execute(
        "INSERT INTO messages(wa_id,role,text,ts) VALUES(?,?,?,?)",
        (wa_id, role, text, int(time.time()))
    )
    con.commit()
    con.close()

def recent_dialog(wa_id: str, limit: int = 10) -> Tuple[str, ...]:
    con = _conn()
    cur = con.execute(
        "SELECT role||': '||text FROM messages WHERE wa_id=? ORDER BY id DESC LIMIT ?",
        (wa_id, limit)
    )
    rows = [r[0] for r in cur.fetchall()]
    con.close()
    return tuple(reversed(rows))
