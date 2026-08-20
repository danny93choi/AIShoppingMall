import re
from typing import Any

SECRET_KEYS = re.compile(r"token|secret|password|authorization|api[_-]?key", re.IGNORECASE)
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE = re.compile(r"(?<!\d)(?:\+?82[- ]?)?0?1[016789][- ]?\d{3,4}[- ]?\d{4}(?!\d)")


def redact_sensitive(value: Any, key: str | None = None) -> Any:
    if key and SECRET_KEYS.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact_sensitive(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        return PHONE.sub("[PHONE]", EMAIL.sub("[EMAIL]", value))
    return value
