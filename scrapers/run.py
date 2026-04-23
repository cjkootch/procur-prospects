"""CLI entry point: `python -m scrapers.run <source1> <source2> ...`

Each source is run, results deduped, and written to
data/output/<source>_<timestamp>.csv plus a combined
data/output/all_companies.csv.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from .models import Company
from .sources.jamaica.gojep_awards import GojepAwardsScraper
from .sources.jamaica.jamaica_chamber import JamaicaChamberScraper
from .sources.jamaica.jampro import JamproScraper
from .sources.jamaica.jmea import JmeaScraper
from .sources.jamaica.psoj import PsojScraper
from .utils.dedupe import dedupe
from .utils.writer import write_csv

SCRAPERS: dict[str, type] = {
    "jmea": JmeaScraper,
    "jamaica_chamber": JamaicaChamberScraper,
    "psoj": PsojScraper,
    "gojep_awards": GojepAwardsScraper,
    "jampro": JamproScraper,
}

ALL_JAMAICA = ["jmea", "jamaica_chamber", "psoj", "gojep_awards", "jampro"]

OUTPUT_DIR = Path("data/output")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs="*", help="source keys or 'all'")
    parser.add_argument("--merge", action="store_true", help="also write combined all_companies.csv")
    args = parser.parse_args(argv)

    sources = args.sources or ALL_JAMAICA
    if sources == ["all"]:
        sources = ALL_JAMAICA

    unknown = [s for s in sources if s not in SCRAPERS]
    if unknown:
        parser.error(f"unknown sources: {unknown}. options: {sorted(SCRAPERS)}")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    all_companies: list[Company] = []
    for key in sources:
        cls = SCRAPERS[key]
        try:
            scraper = cls()
            records = scraper.run()
        except Exception as exc:
            logging.exception("scraper=%s failed: %s", key, exc)
            continue
        all_companies.extend(records)
        out = OUTPUT_DIR / f"{key}_{timestamp}.csv"
        write_csv(out, dedupe(records))
        logging.info("wrote %s (%d deduped)", out, len(dedupe(records)))

    if args.merge or len(sources) > 1:
        merged = dedupe(all_companies)
        combined = OUTPUT_DIR / "all_companies.csv"
        write_csv(combined, merged)
        logging.info("wrote %s (%d total deduped)", combined, len(merged))
    return 0


if __name__ == "__main__":
    sys.exit(main())
