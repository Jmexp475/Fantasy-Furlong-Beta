"""Safe numeric parsing helpers."""
from __future__ import annotations

from typing import Any

_INVALID_MARKERS = {"", "-", "--", "none", "null", "nan", "n/a"}


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in _INVALID_MARKERS:
        return None
    return text


def safe_int(value: Any) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        if "." in text:
            f = float(text)
            if not f.is_integer():
                return None
            return int(f)
        return int(text)
    except Exception:
        return None


def safe_float(value: Any) -> float | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return float(text)
    except Exception:
        return None
