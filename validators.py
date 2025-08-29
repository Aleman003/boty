# validators.py
import re
import phonenumbers

EMAIL_RX = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
GREET_ONLY_RX = re.compile(r"^\s*(hola+|buen[oa]s?\s*(d[ií]as|tardes|noches)?)\s*[!.…]*\s*$", re.I)
NAME_HINT_RX = re.compile(
    r"\b(me llamo|mi nombre es|soy|habla|te saluda)\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+){0,2})\b", re.I
)

def extract_email(text: str) -> str | None:
    m = EMAIL_RX.search(text or "")
    return m.group(0) if m else None

def extract_mx_phone(text: str) -> str | None:
    digits = re.sub(r"\D", "", text or "")
    if not digits: return None
    try:
        n = phonenumbers.parse(digits, "MX")
        if not phonenumbers.is_possible_number(n): return None
        e164 = phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164)  # +5255...
        return e164.replace("+", "")  # 52...
    except:  # fallback
        if digits.startswith("00"): digits = digits[2:]
        if digits.startswith("521") and len(digits) == 13:
            digits = "52" + digits[3:]
        if len(digits) == 10:
            digits = "52" + digits
        return digits if 11 <= len(digits) <= 13 else None
