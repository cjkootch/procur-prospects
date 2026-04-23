"""Government of Jamaica Electronic Procurement (GOJEP) award notices.

Highest-intent prospect source: every company listed here won a public tender.
GOJEP posts awards as individual pages under a paginated index. Selector
assumptions mirror the typical Oracle eProcurement template — adjust when
running against the live site.

We extract the awarded company name and surface it as a Company record with
notes capturing tender title, value, and date so outbound copy can reference
the specific win.
"""
from __future__ import annotations

import re
from typing import Iterable

from ...base import CompanyScraper
from ...models import Company

AWARDS_INDEX_URL = "https://www.gojep.gov.jm/epps/cft/awardNoticesList.do"

SELECTORS = {
    "row": "table tr",
    "award_link": 'a[href*="awardNotices"]',
    "awardee": "td.awardee, .awardee-name, .winner",
    "title": "td.title, .notice-title, h2",
    "value": ".contract-value, .awarded-value, td.value",
    "date": ".award-date, td.date",
    "agency": ".ministry, .issuing-agency",
    "next_page": 'a.next, a[rel="next"]',
}


class GojepAwardsScraper(CompanyScraper):
    source_name = "GOJEP Awards"
    source_url = AWARDS_INDEX_URL
    country = "Jamaica"

    def fetch(self) -> Iterable[Company]:
        url = AWARDS_INDEX_URL
        seen_pages: set[str] = set()
        seen_companies: set[str] = set()
        while url and url not in seen_pages:
            seen_pages.add(url)
            soup = self.soup(url)
            for row in soup.select(SELECTORS["row"]):
                awardee_el = row.select_one(SELECTORS["awardee"])
                if not awardee_el:
                    continue
                name = awardee_el.get_text(strip=True)
                if not name or name.lower() in seen_companies:
                    continue
                seen_companies.add(name.lower())
                title_el = row.select_one(SELECTORS["title"])
                value_el = row.select_one(SELECTORS["value"])
                date_el = row.select_one(SELECTORS["date"])
                agency_el = row.select_one(SELECTORS["agency"])
                link_el = row.select_one(SELECTORS["award_link"])
                notes_parts = []
                if title_el:
                    notes_parts.append(f"won: {title_el.get_text(' ', strip=True)}")
                if value_el:
                    notes_parts.append(f"value: {value_el.get_text(' ', strip=True)}")
                if date_el:
                    notes_parts.append(f"date: {date_el.get_text(' ', strip=True)}")
                if agency_el:
                    notes_parts.append(f"agency: {agency_el.get_text(' ', strip=True)}")
                yield Company(
                    name=name,
                    country=self.country,
                    source=self.source_name,
                    source_url=link_el.get("href") if link_el else url,
                    notes="; ".join(notes_parts) or None,
                    tender_categories=_extract_categories(title_el.get_text(" ", strip=True) if title_el else ""),
                )
            next_el = soup.select_one(SELECTORS["next_page"])
            url = next_el.get("href") if next_el else None


_CATEGORY_KEYWORDS = {
    "construction": ["construction", "build", "renovation", "road", "bridge"],
    "it": ["software", "it services", "computer", "digital", "network"],
    "consulting": ["consulting", "advisory", "professional services"],
    "supply": ["supply", "procurement", "goods"],
    "healthcare": ["medical", "hospital", "pharma", "health"],
    "energy": ["oil", "gas", "energy", "power"],
    "security": ["security", "surveillance"],
    "logistics": ["logistics", "transport", "shipping"],
}


def _extract_categories(text: str) -> list[str]:
    if not text:
        return []
    low = text.lower()
    cats = []
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(k)}\b", low) for k in keywords):
            cats.append(cat)
    return cats
