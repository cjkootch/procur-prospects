"""Government of Jamaica Electronic Procurement (GOJEP) contract award notices.

Highest-intent prospect source: every company listed here won a public tender.

The awards list at `/epps/viewCaNotices.do` is paginated (10 per page,
~1,100 pages / 11k awards in total as of the first live pass).  The
awarded supplier name is NOT in the list table — it lives inside the
per-award PDF notice downloadable from the rightmost column.  We:

1. Walk N pages of the awards list (MAX_PAGES, default 30 = 300 recent awards)
2. Download each `downloadNoticeForES.do?resourceId=...` PDF
3. Extract the "Name of contractor" line and surrounding metadata with
   `pdftotext` (poppler).  If poppler is missing we skip gracefully.

The Jamaica title (`Title`) and Contracting Authority (`PE`) appear in
the list row, so we keep them even when PDF parsing fails.
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from typing import Iterable
from urllib.parse import urljoin

import requests

from ...base import CompanyScraper
from ...models import Company

logger = logging.getLogger(__name__)

AWARDS_INDEX_URL = "https://www.gojep.gov.jm/epps/viewCaNotices.do"
PAGE_URL = "https://www.gojep.gov.jm/epps/viewCaNotices.do?d-16531-p={page}"
MAX_PAGES = 30  # ~300 most recent awards

SELECTORS = {
    "row": "table tr",
    "pdf_link": 'a[href*="downloadNoticeForES.do"]',
    "detail_link": 'a[href*="prepareViewCfTWS.do"]',
}

_CONTRACTOR_RE = re.compile(
    r"Name of contractor\s*\(?\d*\)?\s*\n+\s*(?P<name>[^\n]+)",
    re.I,
)
_CATEGORY_RE = re.compile(
    r"PPC Category Code and Titles\s*\(?\d*\)?\s*\n+\s*(?P<cat>[^\n]+)",
    re.I,
)
_PRICE_RE = re.compile(r"Contract price\s*\(?\d*\)?\s*\n+\s*(?P<price>[^\n]+)", re.I)
_TENDER_CATEGORIES = {
    "construction": ["construction", "build", "renovation", "road", "bridge", "civil"],
    "it": ["software", "it services", "computer", "digital", "network", "information technology"],
    "consulting": ["consulting", "advisory", "professional services"],
    "supply": ["supply", "procurement", "goods", "spares", "equipment"],
    "healthcare": ["medical", "hospital", "pharma", "health", "drug"],
    "energy": ["oil", "gas", "energy", "power", "electrical"],
    "security": ["security", "surveillance"],
    "logistics": ["logistics", "transport", "shipping", "tyres"],
    "food": ["food", "catering", "beverage"],
    "cleaning": ["cleaning", "sanitation", "waste"],
}


class GojepAwardsScraper(CompanyScraper):
    source_name = "GOJEP Awards"
    source_url = AWARDS_INDEX_URL
    country = "Jamaica"

    def __init__(self) -> None:
        super().__init__()
        self._pdftotext = shutil.which("pdftotext")
        if not self._pdftotext:
            logger.warning("pdftotext not found — GOJEP awardee names will be missing (install poppler-utils)")

    def fetch(self) -> Iterable[Company]:
        seen_contractors: set[str] = set()
        for page in range(1, MAX_PAGES + 1):
            url = AWARDS_INDEX_URL if page == 1 else PAGE_URL.format(page=page)
            try:
                soup = self.soup(url)
            except requests.HTTPError as e:
                logger.warning("GOJEP page %d failed: %s", page, e)
                continue
            table = soup.select_one("table")
            if not table:
                continue
            rows = table.select("tr")
            logger.info("GOJEP page %d: %d rows", page, max(0, len(rows) - 1))
            for row in rows[1:]:
                cells = row.select("td")
                if len(cells) < 7:
                    continue
                pe = cells[2].get_text(" ", strip=True)
                title = cells[3].get_text(" ", strip=True)
                amount = cells[4].get_text(" ", strip=True)
                date = cells[5].get_text(" ", strip=True)
                pdf_el = cells[6].select_one(SELECTORS["pdf_link"])
                pdf_url = urljoin(AWARDS_INDEX_URL, pdf_el.get("href")) if pdf_el else None
                detail_el = cells[3].select_one(SELECTORS["detail_link"])
                detail_url = urljoin(AWARDS_INDEX_URL, detail_el.get("href")) if detail_el else None

                contractor, ppc_category, price = None, None, amount
                if pdf_url and self._pdftotext:
                    contractor, ppc_category, price = self._parse_pdf(pdf_url) or (None, None, amount)

                if not contractor:
                    # Without the PDF we have no company name to prospect — skip.
                    continue
                key = contractor.lower().strip()
                if key in seen_contractors:
                    continue
                seen_contractors.add(key)

                notes_parts = [f"won: {title}"]
                if price:
                    notes_parts.append(f"value: {price}")
                if date:
                    notes_parts.append(f"date: {date}")
                if pe:
                    notes_parts.append(f"agency: {pe}")

                yield Company(
                    name=contractor,
                    country=self.country,
                    source=self.source_name,
                    industry=ppc_category,
                    source_url=detail_url or pdf_url or url,
                    notes="; ".join(notes_parts),
                    tender_categories=_classify(f"{title} {ppc_category or ''}"),
                )

    def _parse_pdf(self, url: str):
        try:
            resp = self.get(url)
        except requests.HTTPError as e:
            logger.debug("GOJEP PDF %s failed: %s", url, e)
            return None
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
            fh.write(resp.content)
            path = fh.name
        try:
            proc = subprocess.run(
                [self._pdftotext, "-layout", path, "-"],
                capture_output=True, text=True, timeout=25,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.debug("pdftotext failed on %s: %s", url, e)
            return None
        text = proc.stdout or ""
        contractor = _match(_CONTRACTOR_RE, text, "name")
        category = _match(_CATEGORY_RE, text, "cat")
        price = _match(_PRICE_RE, text, "price")
        return contractor, category, price


def _match(pattern: re.Pattern, text: str, group: str) -> str | None:
    m = pattern.search(text)
    if not m:
        return None
    val = m.group(group).strip()
    return val or None


def _classify(text: str) -> list[str]:
    if not text:
        return []
    low = text.lower()
    out = []
    for cat, kws in _TENDER_CATEGORIES.items():
        if any(re.search(rf"\b{re.escape(k)}\b", low) for k in kws):
            out.append(cat)
    return out
