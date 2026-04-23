"""Private Sector Organization of Jamaica (PSOJ) member list.

PSOJ members are higher-value enterprise prospects. Verify selectors on the
live site; member list tends to be a single page with logo cards.
"""
from __future__ import annotations

from typing import Iterable

from ...base import CompanyScraper
from ...models import Company
from ...utils.normalize import clean_email, clean_phone, clean_website

LISTING_URL = "https://psoj.org/membership/our-members/"

SELECTORS = {
    "card": ".member, .member-card, .elementor-image-box-wrapper, article",
    "name": "h3, h2, .member-name, .elementor-image-box-title",
    "website": 'a[href^="http"]:not([href*="psoj.org"])',
    "email": 'a[href^="mailto:"]',
    "phone": 'a[href^="tel:"]',
    "description": ".elementor-image-box-description, .description",
    "next_page": 'a.next, a[rel="next"]',
}


class PsojScraper(CompanyScraper):
    source_name = "PSOJ"
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
                desc_el = card.select_one(SELECTORS["description"])
                yield Company(
                    name=name,
                    country=self.country,
                    source=self.source_name,
                    website=clean_website(website_el.get("href") if website_el else None),
                    email=clean_email(email_el.get("href", "").replace("mailto:", "")) if email_el else None,
                    phone=clean_phone(phone_el.get("href", "").replace("tel:", "")) if phone_el else None,
                    products_services=desc_el.get_text(" ", strip=True) if desc_el else None,
                    source_url=url,
                )
            next_el = soup.select_one(SELECTORS["next_page"])
            url = next_el.get("href") if next_el else None
