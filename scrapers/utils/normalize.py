from __future__ import annotations

import re
import unicodedata

LEGAL_SUFFIXES = (
    "limited", "ltd", "plc", "inc", "incorporated", "llc", "ltda",
    "sa", "s a", "ca", "c a", "srl", "s r l", "co", "company",
    "corp", "corporation", "lp", "llp", "nv", "bv", "gmbh", "ag",
)

_STRIP_PUNCT_RE = re.compile(r"[.,&/()\-'\"]+")
_WS_RE = re.compile(r"\s+")


def strip_accents(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


def normalize_company_name(raw: str) -> str:
    """Lowercase, strip legal suffixes and punctuation, collapse whitespace."""
    if not raw:
        return ""
    value = strip_accents(raw).lower()
    value = _STRIP_PUNCT_RE.sub(" ", value)
    tokens = _WS_RE.sub(" ", value).strip().split()
    tokens = [t for t in tokens if t not in LEGAL_SUFFIXES]
    return " ".join(tokens).strip()


def clean_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = re.sub(r"[^\d+]", "", raw)
    if len(cleaned) < 7:
        return None
    return cleaned


def clean_email(raw: str | None) -> str | None:
    if not raw:
        return None
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", raw)
    return match.group(0).lower() if match else None


def clean_website(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip()
    if not value:
        return None
    if not value.startswith("http"):
        value = "https://" + value.lstrip("/")
    return value
