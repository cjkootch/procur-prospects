"""Jamaica Chamber of Commerce member directory.

As of the first scraping pass the public directory page at
https://jamaicachamber.org.jm/member-directory/ renders a literal
"Directory Coming Soon" placeholder — no member cards, no API.  Until
the directory goes live, we fall back to scraping the `members_articles`
sitemap, which profiles a small number of featured members.  Company
names surface from the article slug; we stash the article URL under
`source_url` so a human can verify.

When the official directory ships, update SELECTORS and the main loop
in `fetch_directory()` to parse real cards.
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

LISTING_URL = "https://jamaicachamber.org.jm/member-directory/"
ARTICLES_SITEMAP = "https://jamaicachamber.org.jm/members_articles-sitemap.xml"

SELECTORS = {
    "card": ".member, .directory-entry, .member-card, article.member",
    "name": "h3, h2, .member-name",
    "website": 'a[href^="http"]:not([href*="jamaicachamber.org.jm"])',
    "email": 'a[href^="mailto:"]',
    "phone": 'a[href^="tel:"]',
    "address": ".address, .member-address",
    "industry": ".member-category, .industry",
    "next_page": 'a.next, a[rel="next"]',
}

_COMING_SOON_RE = re.compile(r"coming\s+soon", re.I)
_SUFFIX_RE = re.compile(
    r"\b(celebrates?|supports?|joins?|talks?|calls?|calling|discussing|ceo|10th|anniversary|"
    r"business|forbes|solutions|smes|ghana|jamaica|indonesian|nigeria|removal|cost|financing"
    r").*$",
    re.I,
)


class JamaicaChamberScraper(CompanyScraper):
    source_name = "Jamaica Chamber"
    source_url = LISTING_URL
    country = "Jamaica"

    def fetch(self) -> Iterable[Company]:
        yielded = list(self._fetch_directory())
        if yielded:
            yield from yielded
            return
        logger.info("Jamaica Chamber directory empty / 'Coming Soon' — falling back to members_articles sitemap")
        yield from self._fetch_from_articles_sitemap()

    def _fetch_directory(self) -> Iterable[Company]:
        url = LISTING_URL
        seen: set[str] = set()
        while url and url not in seen:
            seen.add(url)
            try:
                soup = self.soup(url)
            except requests.HTTPError as e:
                logger.warning("Jamaica Chamber %s failed: %s", url, e)
                return
            if _COMING_SOON_RE.search(soup.get_text(" ", strip=True)[:2000]):
                return
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

    def _fetch_from_articles_sitemap(self) -> Iterable[Company]:
        try:
            resp = self.get(ARTICLES_SITEMAP)
        except requests.HTTPError as e:
            logger.warning("Jamaica Chamber articles sitemap failed: %s", e)
            return
        urls = re.findall(r"<loc>([^<]+)</loc>", resp.text)
        seen_names: set[str] = set()
        for article_url in urls:
            if "/members_articles/" not in article_url or article_url.endswith("/members_articles/"):
                continue
            slug = article_url.rstrip("/").rsplit("/", 1)[-1]
            name = _name_from_slug(slug)
            if not name or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            yield Company(
                name=name,
                country=self.country,
                source=self.source_name,
                source_url=article_url,
                notes="sourced from JCC members_articles sitemap (full directory 'Coming Soon')",
            )


def _name_from_slug(slug: str) -> str:
    text = slug.replace("-", " ").title()
    text = _SUFFIX_RE.sub("", text).strip(" ,-")
    # Remove trailing 'Of', 'Joins' etc left by simple title-case
    text = re.sub(r"\b(Of|To|The|For|On|In|At|With|And)\s*$", "", text).strip()
    return text if len(text) >= 3 else ""
