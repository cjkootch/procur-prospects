"""Jamaica Manufacturers & Exporters Association member directory.

The public directory lives at https://jmea.org/listings/ — a paginated grid
of cards (48 per page, currently 13 pages ≈ ~600 members).  Each card links
to a detail page where the phone and email live inside a `<ul class="ul-disc">`
list of "Phone : ..." / "Email : ..." bullet points.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable

import requests

from ...base import CompanyScraper
from ...models import Company
from ...utils.normalize import clean_email, clean_phone, clean_website

logger = logging.getLogger(__name__)

LISTING_URL = "https://jmea.org/listings/"
PAGE_URL = "https://jmea.org/listings/page/{page}/"
MAX_PAGES = 20  # safety cap; site currently has ~13

SELECTORS = {
    "card": ".listingdata-col",
    "name": "a.title",
    "category": ".address",          # misnamed upstream — holds industry label
    "detail_link": "a.title",
    "pagination_last": ".pagination a.page-numbers",
    "detail_fields": "ul.ul-disc li",
    "detail_website": ".listing-overview a[href^='http']",
}

_PHONE_PREFIX_RE = re.compile(r"^\s*(phone|tel|telephone|mobile)\s*[:\-]\s*", re.I)
_EMAIL_PREFIX_RE = re.compile(r"^\s*(email|e-mail)\s*[:\-]\s*", re.I)
_WEB_PREFIX_RE = re.compile(r"^\s*(website|web)\s*[:\-]\s*", re.I)
_ADDR_PREFIX_RE = re.compile(r"^\s*(address|location)\s*[:\-]\s*", re.I)


class JmeaScraper(CompanyScraper):
    source_name = "JMEA"
    source_url = LISTING_URL
    country = "Jamaica"
    delay_seconds = 1.5  # site has ~600 detail pages; 3s each would blow the 3h CI timeout

    def fetch(self) -> Iterable[Company]:
        # Walk pages forward until we hit one with no cards (or 404) rather than
        # relying on a fragile pagination-count discovery selector that's
        # occasionally missing depending on what upstream serves.
        for page in range(1, MAX_PAGES + 1):
            url = LISTING_URL if page == 1 else PAGE_URL.format(page=page)
            try:
                soup = self.soup(url)
            except requests.RequestException as e:
                logger.warning("JMEA page %d failed (%s) — skipping page", page, e)
                continue
            cards = soup.select(SELECTORS["card"])
            logger.info("JMEA page %d: %d cards", page, len(cards))
            if not cards:
                logger.info("JMEA stopping at page %d (no cards)", page)
                break
            for card in cards:
                name_el = card.select_one(SELECTORS["name"])
                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                if not name:
                    continue
                detail_url = name_el.get("href") or ""
                cat_el = card.select_one(SELECTORS["category"])
                industry = cat_el.get_text(" ", strip=True) if cat_el else None

                phone = email = website = address = None
                products = None
                if detail_url:
                    phone, email, website, address, products = self._fetch_detail(detail_url)

                yield Company(
                    name=name,
                    country=self.country,
                    source=self.source_name,
                    website=website,
                    email=email,
                    phone=phone,
                    address=address,
                    industry=industry,
                    products_services=products,
                    source_url=detail_url or url,
                )

    def _discover_page_count(self) -> int:
        """Kept for external callers; the main loop now walks until empty."""
        try:
            soup = self.soup(LISTING_URL)
        except requests.RequestException as e:
            logger.warning("JMEA root listing failed (%s) — assuming 1 page", e)
            return 1
        pages = []
        for a in soup.select(SELECTORS["pagination_last"]):
            txt = a.get_text(strip=True)
            if txt.isdigit():
                pages.append(int(txt))
        return min(max(pages) if pages else 1, MAX_PAGES)

    def _fetch_detail(self, url: str):
        try:
            soup = self.soup(url)
        except requests.RequestException as e:
            logger.debug("JMEA detail %s failed (%s)", url, e)
            return None, None, None, None, None
        phone = email = website = address = products = None
        for li in soup.select(SELECTORS["detail_fields"]):
            txt = li.get_text(" ", strip=True)
            if not txt:
                continue
            if _PHONE_PREFIX_RE.match(txt):
                a = li.select_one('a[href^="tel:"]')
                raw = a.get("href", "").replace("tel:", "") if a else _PHONE_PREFIX_RE.sub("", txt)
                phone = clean_phone(raw) or phone
            elif _EMAIL_PREFIX_RE.match(txt):
                a = li.select_one('a[href^="mailto:"]')
                raw = a.get("href", "").replace("mailto:", "") if a else _EMAIL_PREFIX_RE.sub("", txt)
                email = clean_email(raw) or email
            elif _WEB_PREFIX_RE.match(txt):
                a = li.select_one('a[href^="http"]')
                raw = a.get("href") if a else _WEB_PREFIX_RE.sub("", txt)
                website = clean_website(raw) or website
            elif _ADDR_PREFIX_RE.match(txt):
                address = _ADDR_PREFIX_RE.sub("", txt) or address
        overview = soup.select_one(".listing-overview")
        if overview:
            desc = overview.select_one("p")
            if desc:
                products = desc.get_text(" ", strip=True) or None
        return phone, email, website, address, products
