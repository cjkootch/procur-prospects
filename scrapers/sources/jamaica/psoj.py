"""Private Sector Organization of Jamaica (PSOJ) council members.

PSOJ does not publish a full member directory publicly; the closest
canonical list is the council-members page, which enumerates the
Corporate, Associations, and Overseas Associate members elected each
year.  That gives us ~45 high-value enterprise records.

The page layout is:

    <p>Corporate:</p>
    <ol><li>Appliance Traders Limited</li>...</ol>
    <p>Associations:</p>
    <ol><li>Global Services Association</li>...</ol>

Individuals are skipped — they are people, not companies.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable

import requests

from ...base import CompanyScraper
from ...models import Company

logger = logging.getLogger(__name__)

LISTING_URL = "https://www.psoj.org/council-members/"

SECTION_HEADERS = {
    "corporate": "Corporate",
    "associations": "Associations",
    "overseas": "Overseas Associate",
}

_SECTION_TEXT_RE = re.compile(
    r"^\s*(corporate|associations?|overseas(?:\s+associate)?)\s*:?\s*$",
    re.I,
)


class PsojScraper(CompanyScraper):
    source_name = "PSOJ"
    source_url = LISTING_URL
    country = "Jamaica"

    def fetch(self) -> Iterable[Company]:
        try:
            soup = self.soup(LISTING_URL)
        except requests.HTTPError as e:
            logger.warning("PSOJ council-members fetch failed: %s", e)
            return
        main = soup.select_one(".entry-content") or soup.body
        if not main:
            return
        for nav in main.select("nav, header, footer"):
            nav.decompose()

        current_section: str | None = None
        for el in main.descendants:
            name = getattr(el, "name", None)
            if name == "p":
                text = el.get_text(" ", strip=True)
                # The page renders "Oversea s Associate" with a stray space/newline.
                normalized = re.sub(r"\s+", " ", text).strip().rstrip(":")
                m = _SECTION_TEXT_RE.match(normalized)
                if m:
                    current_section = m.group(1).lower()
                    if current_section.startswith("overseas"):
                        current_section = "overseas"
                    elif current_section.startswith("association"):
                        current_section = "associations"
            elif name == "ol" and current_section:
                category_label = {
                    "corporate": "Corporate member",
                    "associations": "Industry association",
                    "overseas": "Overseas associate",
                }[current_section]
                for li in el.find_all("li", recursive=False) or el.select("li"):
                    company_name = li.get_text(" ", strip=True)
                    if not company_name:
                        continue
                    yield Company(
                        name=company_name,
                        country=self.country,
                        source=self.source_name,
                        industry=category_label,
                        source_url=LISTING_URL,
                    )
                current_section = None
