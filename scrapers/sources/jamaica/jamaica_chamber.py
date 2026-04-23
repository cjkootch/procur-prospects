"""Jamaica Chamber of Commerce member directory.

Selectors are best-guess; verify against the live site and tune as needed.
"""
from __future__ import annotations

from typing import Iterable

from ...base import CompanyScraper
from ...models import Company
from ...utils.normalize import clean_email, clean_phone, clean_website

LISTING_URL = "https://www.jamaicachamber.org.jm/member-directory"

SELECTORS = {
    "card": ".member, .directory-entry, .member-card, article",
    "name": "h3, h2, .member-name",
    "website": 'a[href^="http"]:not([href*="jamaicachamber.org.jm"])',
    "email": 'a[href^="mailto:"]',
    "phone": 'a[href^="tel:"]',
    "address": ".address, .member-address",
    "industry": ".member-category, .industry",
    "next_page": 'a.next, a[rel="next"]',
}


class JamaicaChamberScraper(CompanyScraper):
    source_name = "Jamaica Chamber"
    source_url = LISTING_URL
    country = "Jamaica"

    def fetch(self) -> Iterable[Company]:
        url = LISTING_URL
        seen: set[str] = set()
        while url and url not in seen:
            seen.add(url)
            soup = self.soup(url)
            for card in soup.select(SELECTORS["card"]):
                name_el = card.select_one(SELECTORS["name"])
                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                if not name:
                    continue
                website_el = card.select_one(SELECTORS["website"])
                email_el = card.select_one(SELECTORS["email"])
                phone_el = card.select_one(SELECTORS["phone"])
                addr_el = card.select_one(SELECTORS["address"])
                industry_el = card.select_one(SELECTORS["industry"])
                yield Company(
                    name=name,
                    country=self.country,
                    source=self.source_name,
                    website=clean_website(website_el.get("href") if website_el else None),
                    email=clean_email(email_el.get("href", "").replace("mailto:", "")) if email_el else None,
                    phone=clean_phone(phone_el.get("href", "").replace("tel:", "")) if phone_el else None,
                    address=addr_el.get_text(" ", strip=True) if addr_el else None,
                    industry=industry_el.get_text(strip=True) if industry_el else None,
                    source_url=url,
                )
            next_el = soup.select_one(SELECTORS["next_page"])
            url = next_el.get("href") if next_el else None
