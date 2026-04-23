from __future__ import annotations

from rapidfuzz import fuzz

from ..models import Company
from .normalize import normalize_company_name

FUZZY_THRESHOLD = 88  # 0-100


def _key(company: Company) -> tuple[str, str]:
    return (normalize_company_name(company.name), (company.country or "").lower())


def merge(existing: Company, incoming: Company) -> Company:
    """Merge incoming into existing: prefer non-empty incoming values,
    keep existing source/source_url as primary, note the extra source."""
    for attr in (
        "website", "email", "phone", "address", "industry",
        "sub_industry", "contact_person", "contact_title",
        "products_services", "notes",
    ):
        if not getattr(existing, attr) and getattr(incoming, attr):
            setattr(existing, attr, getattr(incoming, attr))
    for cat in incoming.tender_categories:
        if cat not in existing.tender_categories:
            existing.tender_categories.append(cat)
    extra = f"also in {incoming.source}"
    if incoming.source and incoming.source != existing.source:
        existing.notes = f"{existing.notes}; {extra}" if existing.notes else extra
    return existing


def dedupe(companies: list[Company]) -> list[Company]:
    """Collapse duplicates using normalized-name + country with fuzzy
    fallback within the same country."""
    by_key: dict[tuple[str, str], Company] = {}
    for c in companies:
        if not c.name:
            continue
        key = _key(c)
        if not key[0]:
            continue
        if key in by_key:
            by_key[key] = merge(by_key[key], c)
            continue
        # Fuzzy fallback: check against companies from the same country.
        matched_key = None
        best = 0
        for k in by_key:
            if k[1] != key[1]:
                continue
            score = fuzz.token_sort_ratio(k[0], key[0])
            if score > best:
                best = score
                matched_key = k
        if matched_key and best >= FUZZY_THRESHOLD:
            by_key[matched_key] = merge(by_key[matched_key], c)
        else:
            by_key[key] = c
    return list(by_key.values())
