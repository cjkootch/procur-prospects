from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from .models import Company

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "procur-prospects/0.1 (+contact cole@procur.app)"
DEFAULT_DELAY_SECONDS = 3.0
DEFAULT_TIMEOUT_SECONDS = 25


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
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})

    @abstractmethod
    def fetch(self) -> Iterable[Company]:
        """Yield Company records from the source."""

    def get(self, url: str, **kwargs) -> requests.Response:
        time.sleep(self.delay_seconds)
        kwargs.setdefault("timeout", DEFAULT_TIMEOUT_SECONDS)
        resp = self.session.get(url, **kwargs)
        resp.raise_for_status()
        return resp

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
