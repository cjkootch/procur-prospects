"""JAMPRO exporter directory (Playwright, JS-heavy).

The JAMPRO directory is rendered client-side, so we use Playwright to load
each listing page, scroll through results, and extract company cards.

Run `playwright install chromium` after installing requirements.
"""
from __future__ import annotations

import logging
from typing import Iterable

from ...base import CompanyScraper
from ...models import Company
from ...utils.normalize import clean_email, clean_phone, clean_website

logger = logging.getLogger(__name__)

LISTING_URL = "https://www.jamprocorp.com/exporter-directory/"

# Update these after inspecting the live page's DOM.
SELECTORS = {
    "card": ".exporter-card, .company-card, article",
    "name": "h3, h2, .company-name",
    "website": 'a[href^="http"]:not([href*="jamprocorp.com"])',
    "email": 'a[href^="mailto:"]',
    "phone": 'a[href^="tel:"]',
    "address": ".company-address, .address",
    "industry": ".industry, .category, .sector",
    "products": ".products, .services, .description",
    "next_page": 'a.next, a[rel="next"], button:has-text("Next")',
}

MAX_SCROLLS = 40


class JamproScraper(CompanyScraper):
    source_name = "JAMPRO"
    source_url = LISTING_URL
    country = "Jamaica"

    def fetch(self) -> Iterable[Company]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "Playwright not installed. Run `pip install playwright && playwright install chromium`."
            ) from e

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=self.session.headers["User-Agent"])
            page = ctx.new_page()
            page.goto(LISTING_URL, wait_until="networkidle", timeout=45000)
            # Scroll to trigger lazy loading of all entries.
            last_count = 0
            for _ in range(MAX_SCROLLS):
                page.mouse.wheel(0, 4000)
                page.wait_for_timeout(1000)
                count = page.locator(SELECTORS["card"]).count()
                if count == last_count:
                    break
                last_count = count
            cards = page.locator(SELECTORS["card"])
            total = cards.count()
            logger.info("JAMPRO cards found: %d", total)
            for i in range(total):
                card = cards.nth(i)
                try:
                    name = (card.locator(SELECTORS["name"]).first.inner_text(timeout=2000) or "").strip()
                except Exception:
                    continue
                if not name:
                    continue
                website = _safe_attr(card, SELECTORS["website"], "href")
                email_href = _safe_attr(card, SELECTORS["email"], "href")
                phone_href = _safe_attr(card, SELECTORS["phone"], "href")
                address = _safe_text(card, SELECTORS["address"])
                industry = _safe_text(card, SELECTORS["industry"])
                products = _safe_text(card, SELECTORS["products"])
                yield Company(
                    name=name,
                    country=self.country,
                    source=self.source_name,
                    website=clean_website(website),
                    email=clean_email(email_href.replace("mailto:", "")) if email_href else None,
                    phone=clean_phone(phone_href.replace("tel:", "")) if phone_href else None,
                    address=address,
                    industry=industry,
                    products_services=products,
                    source_url=LISTING_URL,
                )
            browser.close()


def _safe_text(card, selector: str) -> str | None:
    try:
        loc = card.locator(selector).first
        if loc.count() == 0:
            return None
        return (loc.inner_text(timeout=1500) or "").strip() or None
    except Exception:
        return None


def _safe_attr(card, selector: str, attr: str) -> str | None:
    try:
        loc = card.locator(selector).first
        if loc.count() == 0:
            return None
        return loc.get_attribute(attr, timeout=1500)
    except Exception:
        return None
