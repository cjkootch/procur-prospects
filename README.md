# Procur Prospects — V0

Jamaica-first prospect scraper. Pulls companies from public business directories and government tender award notices, deduplicates across sources, and writes one CSV per source plus a combined `all_companies.csv` ready for manual HubSpot import.

No database, no Apollo, no HubSpot API. Ship the list, email the list.

## Sources (Jamaica only in V0)

| Key | Source | Type | Playwright? |
|---|---|---|---|
| `jmea` | Jamaica Manufacturers & Exporters Association | member directory | no |
| `jamaica_chamber` | Jamaica Chamber of Commerce | member directory | no |
| `psoj` | Private Sector Organization of Jamaica | member directory | no |
| `gojep_awards` | Government eProcurement award notices | awards feed | no |
| `jampro` | JAMPRO exporter directory | exporter registry | **yes** |

## Quick start

### Run in GitHub Actions (recommended)

1. Push this repo to GitHub.
2. Actions → **Scrape** → **Run workflow**. Leave sources blank to scrape all five Jamaica sources, or pass e.g. `jmea jamaica_chamber` to target specific ones.
3. When the job finishes, it commits the output CSVs to `data/output/` on the same branch. Download `data/output/all_companies.csv` and import into HubSpot.

### Run locally

```bash
pip install -r requirements.txt
playwright install chromium   # only needed if running JAMPRO

# single source
python -m scrapers.run jmea

# all Jamaica sources, with combined output
python -m scrapers.run --merge
```

Output lands in `data/output/`.

## Output schema

Every CSV has these columns (aligned with HubSpot's company + contact fields for easy mapping):

```
name, country, source, website, email, phone, address,
industry, sub_industry, contact_person, contact_title,
products_services, tender_categories, source_url, notes
```

`tender_categories` is semicolon-separated. `notes` captures auxiliary context such as tender title/value/date when the source is GOJEP Awards — useful for personalized outbound copy ("Congrats on winning the [tender title] contract with [ministry]").

## HubSpot import (manual)

1. Open `data/output/all_companies.csv`.
2. In HubSpot, go to Contacts → Import → File from computer → One file → One object → **Company**.
3. Map columns:
   - `name` → Company name
   - `website` → Company domain name
   - `phone` → Phone number
   - `address` → Street address
   - `industry` → Industry
   - `country` → Country/Region
   - `source` → custom property `procur_source`
   - `tender_categories` → custom property `procur_tender_categories`
   - `notes` → custom property `procur_notes`
4. Create a list segmenting on `procur_source IS ANY OF [JMEA, PSOJ, GOJEP Awards, ...]` to target outbound campaigns by source.

For contacts (decision-makers), the `contact_person`, `contact_title`, `email`, `phone` columns can be imported separately as a Contact object associated to the Company by `name` or website.

## Deduplication

Companies are collapsed to one row using:
1. Exact match on normalized name + country (legal suffixes like Ltd/Limited/Inc/S.A. stripped, accents removed).
2. Fuzzy fallback at 88% token-sort ratio within the same country (catches "Caribbean Steel Works Ltd" vs "Caribbean Steelworks Limited").

When duplicates merge, the first-seen source stays primary; additional sources are appended to `notes` as `also in <source>`.

## Adding a new source

1. Create `scrapers/sources/<country>/<slug>.py` subclassing `CompanyScraper`.
2. Implement `fetch()` as a generator yielding `Company` records.
3. Register the key in `scrapers/run.py` SCRAPERS dict.
4. Add to the `SCRAPERS` matrix in `.github/workflows/scrape.yml` if you want it in scheduled runs.

## Known limitations / next steps

- **Selector assumptions are unverified.** The scrapers were written without being able to reach the target sites from the build environment. First real GH Actions run will likely yield low counts on one or two sources; tighten the `SELECTORS` dict at the top of each scraper when you see zero results or empty fields.
- **No JAMPRO yet if Playwright isn't installed.** The workflow installs it; local runs need `playwright install chromium`.
- **GOJEP awards** may require table-row parsing different from the generic template. Will likely need the first pass, then a tweak.
- **No contact enrichment.** Emails/phones captured are only those the source publishes. Apollo/Hunter integration is deferred to V1.
- **V0 is Jamaica only.** Trinidad, Guyana, DR, Barbados scrapers are scoped for V1.

## Running the tests

```bash
python -m pytest -q
```

Covers the dedupe + normalization logic, which is the only non-IO piece.
