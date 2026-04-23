"""JAMPRO exporter directory.

JAMPRO's public "Exporter Directory" is distributed as a single PDF
hosted on the Do Business Jamaica site
(https://dobusinessjamaica.com/wp-content/uploads/2019/11/Exporter-Directory-2018.pdf).
No live HTML listing exists; the corporate `jamprocorp.com` domain is
intermittently unreachable and the DBJ directory landing page simply
links to the PDF.

The PDF is 3-column per page. We extract text with `pdftotext -layout`,
discover the per-page column offsets by looking at where each
`Category:` line starts (the layout drifts by a couple of characters
between pages), slice each page into columns, and treat each
blank-line-separated block as one exporter record.

Record format inside each column:

    Company Name
    Contact Person
    Address line 1
    Address line 2
    T: <phone numbers>
    E: <email(s)>          (optional)
    W: <website>           (optional)
    Category: <industry>   (may wrap onto a second line)
    Product: <products>    (may wrap onto multiple lines)
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from typing import Iterable

import requests

from ...base import CompanyScraper
from ...models import Company
from ...utils.normalize import clean_email, clean_phone, clean_website

logger = logging.getLogger(__name__)

PDF_URL = "https://dobusinessjamaica.com/wp-content/uploads/2019/11/Exporter-Directory-2018.pdf"
LISTING_PAGE_URL = "https://dobusinessjamaica.com/export/exporter-directory/"

HEADER_WORDS = {"EXPORTER", "DIRECTORY", "2018", "LIST OF COMPANIES"}

_CATEGORY_RE = re.compile(r"\bCategory:")
_PAGE_NUM_RE = re.compile(r"^\d{1,3}$")


class JamproScraper(CompanyScraper):
    source_name = "JAMPRO"
    source_url = LISTING_PAGE_URL
    country = "Jamaica"

    def __init__(self) -> None:
        super().__init__()
        self._pdftotext = shutil.which("pdftotext")
        if not self._pdftotext:
            raise RuntimeError(
                "pdftotext not found. Install poppler-utils (apt install poppler-utils)."
            )

    def fetch(self) -> Iterable[Company]:
        try:
            resp = self.get(PDF_URL)
        except requests.HTTPError as e:
            logger.warning("JAMPRO PDF fetch failed: %s", e)
            return

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
            fh.write(resp.content)
            pdf_path = fh.name

        try:
            proc = subprocess.run(
                [self._pdftotext, "-layout", pdf_path, "-"],
                capture_output=True, text=True, timeout=60,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning("pdftotext failed on JAMPRO PDF: %s", e)
            return

        text = proc.stdout or ""
        # Bracket to the company list portion.
        first_cat = text.find("Category:")
        if first_cat < 0:
            logger.warning("JAMPRO PDF had no Category: lines — layout may have changed")
            return
        start = text.rfind("LIST OF COMPANIES", 0, first_cat)
        end = text.find("HARMONISED")
        chunk = text[start:end] if start >= 0 and end > start else text[:end if end > 0 else None]

        for record in self._iter_records(chunk):
            parsed = self._parse_record(record)
            if parsed:
                yield parsed

    def _iter_records(self, chunk: str) -> Iterable[list[str]]:
        for page in chunk.split("\f"):
            if not page.strip():
                continue
            lines = page.split("\n")
            col_bounds = self._column_bounds(page)
            for stream in self._split_columns(lines, col_bounds):
                buf: list[str] = []
                for line in stream:
                    stripped = line.strip()
                    if stripped in HEADER_WORDS or _PAGE_NUM_RE.fullmatch(stripped):
                        continue
                    if not stripped:
                        if buf:
                            yield buf
                            buf = []
                    else:
                        buf.append(stripped)
                if buf:
                    yield buf

    def _column_bounds(self, page: str) -> list[tuple[int, int | None]]:
        """Infer 3-column left edges for a page by looking at Category: line starts."""
        cols: set[int] = set()
        for m in _CATEGORY_RE.finditer(page):
            line_start = page.rfind("\n", 0, m.start()) + 1
            cols.add(m.start() - line_start)
        ordered = sorted(cols)[:3]
        if len(ordered) < 3:
            ordered = [0, 51, 100]
        ordered[0] = 0  # ensure column 0 starts at 0
        return [(ordered[i], ordered[i + 1] if i + 1 < len(ordered) else None) for i in range(len(ordered))]

    def _split_columns(self, lines: list[str], bounds: list[tuple[int, int | None]]) -> list[list[str]]:
        streams: list[list[str]] = [[] for _ in bounds]
        for line in lines:
            for i, (a, b) in enumerate(bounds):
                seg = (line[a:b] if b is not None else line[a:]).rstrip()
                streams[i].append(seg)
        return streams

    def _parse_record(self, lines: list[str]) -> Company | None:
        if not any(l.startswith("Category:") for l in lines):
            return None
        name = lines[0].strip()
        if not name or len(name) > 160:
            return None

        contact_person = ""
        if len(lines) > 1 and not lines[1].startswith(("T:", "E:", "W:", "Category:", "Product:")):
            contact_person = lines[1].strip()

        # Address: lines between (contact or name) and first T:/E:/W:/Category:
        addr_start = 2 if contact_person else 1
        addr_lines: list[str] = []
        phone = email = website = ""
        category_lines: list[str] = []
        product_lines: list[str] = []
        section: str | None = None
        for idx, line in enumerate(lines[addr_start:], start=addr_start):
            if line.startswith("T:"):
                phone = line[len("T:"):].strip(); section = "t"
            elif line.startswith("E:"):
                email = line[len("E:"):].strip(); section = "e"
            elif line.startswith("W:"):
                website = line[len("W:"):].strip(); section = "w"
            elif line.startswith("Category:"):
                category_lines.append(line[len("Category:"):].strip()); section = "c"
            elif line.startswith("Product:"):
                product_lines.append(line[len("Product:"):].strip()); section = "p"
            else:
                if section is None:
                    addr_lines.append(line)
                elif section == "c":
                    category_lines.append(line)
                elif section == "p":
                    product_lines.append(line)
                elif section == "e":
                    # additional email line
                    email += " " + line
                elif section == "w":
                    website += " " + line
                elif section == "t":
                    phone += " " + line

        category = ", ".join(p for p in (s.strip(" ,") for s in category_lines) if p) or None
        products = " ".join(p for p in product_lines if p).strip() or None
        address = ", ".join(a.rstrip(",") for a in addr_lines if a).strip(", ") or None

        # Pick the first phone number if multiple are semicolon-separated.
        primary_phone = phone.split(";")[0] if phone else ""
        primary_email = email.split(";")[0].split(",")[0] if email else ""
        primary_website = website.split(";")[0] if website else ""

        return Company(
            name=name,
            country=self.country,
            source=self.source_name,
            website=clean_website(primary_website) if primary_website else None,
            email=clean_email(primary_email) if primary_email else None,
            phone=clean_phone(primary_phone) if primary_phone else None,
            address=address,
            industry=category,
            contact_person=contact_person or None,
            products_services=products,
            source_url=PDF_URL,
        )
