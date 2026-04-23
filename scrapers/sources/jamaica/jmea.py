"""Jamaica Manufacturers & Exporters Association member directory.

Selector assumptions below are based on typical WordPress business-directory
plugins. Run against the live site, inspect the HTML, and tighten SELECTORS
if the output count is zero or fields come back empty.
"""
from __future__ import annotations

from typing import Iterable

from ...base import CompanyScraper
from ...models import Company
from ...utils.normalize import clean_email, clean_phone, clean_website

LISTING_URL = "https://jmea.org/member-directory/"

SELECTORS = {
    "card": ".member, .directory-item, article.member, .wpbdp-listing",
    "name": "h3, h2, .member-name, .listing-title",
    "website": 'a[href^="http"]:not([href*="jmea.org"])',
    "email": 'a[href^="mailto:"]',
    "phone": 'a[href^="tel:"]',
    "address": ".member-address, .address",
    "industry": ".member-category, .category",
    "next_page": 'a.next, a[rel="next"]',
}


class JmeaScraper(CompanyScraper):
    source_name = "JMEA"
    source_url = LISTING_URL
    country = "Jamaica"

    def fetch(self) -> Iterable[Company]:
        url = LISTING_URL
        seen_urls: set[str] = set()
        while url and url not in seen_urls:
            seen_urls.add(url)
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
