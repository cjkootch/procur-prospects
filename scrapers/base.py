from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from .models import Company

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 procur-prospects/0.1"
)
DEFAULT_DELAY_SECONDS = 3.0
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF = 4.0


class CompanyScraper(ABC):
    """Base class for directory/awards scrapers.

    Subclasses set source_name/source_url/country and implement fetch()
    to yield Company records. fetch() can be a generator so large
    directories stream to disk rather than materializing in memory.
    """

    source_name: str = ""
    source_url: str = ""
    country: str = ""
    delay_seconds: float = DEFAULT_DELAY_SECONDS

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    @abstractmethod
    def fetch(self) -> Iterable[Company]:
        """Yield Company records from the source."""

    def get(self, url: str, **kwargs) -> requests.Response:
        """GET with polite delay + exponential backoff on 5xx and timeouts."""
        time.sleep(self.delay_seconds)
        kwargs.setdefault("timeout", DEFAULT_TIMEOUT_SECONDS)
        last_exc: Exception | None = None
        for attempt in range(DEFAULT_RETRY_ATTEMPTS):
            try:
                resp = self.session.get(url, **kwargs)
                if resp.status_code >= 500:
                    raise requests.HTTPError(f"{resp.status_code} server error", response=resp)
                resp.raise_for_status()
                return resp
            except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as e:
                last_exc = e
                wait = DEFAULT_RETRY_BACKOFF * (2 ** attempt)
                logger.info("retry %d for %s (%s) in %.1fs", attempt + 1, url, e, wait)
                time.sleep(wait)
        assert last_exc is not None
        raise last_exc

    def soup(self, url: str, **kwargs) -> BeautifulSoup:
        return BeautifulSoup(self.get(url, **kwargs).text, "html.parser")

    def run(self) -> list[Company]:
        """Run fetch(), log progress, return materialized list."""
        logger.info("scraper=%s starting", self.source_name)
        companies: list[Company] = []
        for c in self.fetch():
            c.source = c.source or self.source_name
            c.country = c.country or self.country
            companies.append(c)
            if len(companies) % 25 == 0:
                logger.info("scraper=%s collected=%d", self.source_name, len(companies))
        logger.info("scraper=%s done total=%d", self.source_name, len(companies))
        return companies
