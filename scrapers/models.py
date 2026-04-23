from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Company:
    """Canonical company record produced by every scraper."""

    name: str
    country: str
    source: str
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    industry: Optional[str] = None
    sub_industry: Optional[str] = None
    contact_person: Optional[str] = None
    contact_title: Optional[str] = None
    products_services: Optional[str] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None
    tender_categories: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tender_categories"] = ";".join(self.tender_categories) if self.tender_categories else ""
        return d


CSV_FIELDS = [
    "name",
    "country",
    "source",
    "website",
    "email",
    "phone",
    "address",
    "industry",
    "sub_industry",
    "contact_person",
    "contact_title",
    "products_services",
    "tender_categories",
    "source_url",
    "notes",
]
