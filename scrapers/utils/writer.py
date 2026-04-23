from __future__ import annotations

import csv
from pathlib import Path

from ..models import CSV_FIELDS, Company


def write_csv(path: Path, companies: list[Company]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for c in companies:
            row = c.to_dict()
            writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})
