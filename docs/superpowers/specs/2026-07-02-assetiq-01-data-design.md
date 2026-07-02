# AssetIQ — Phase 01: Data & Scraper

**Track:** Data
**Depends on:** 00 (SQLite schema, `.env` keys, data dictionary)
**Gate:** ⛔ **Gate 1** — scraper design review, then live sample-run review before bulk scraping.

## Objective

Populate SQLite with two datasets: the cleaned `merc.csv` training corpus (in RM), and **real**
second-hand Mercedes listings scraped politely from Mudah.my and Carlist.my. Never fabricate
listings.

## Consumes

- `training_data`, `market_listings` table schemas (Phase 00).
- `FX_GBP_TO_RM`, `SCRAPER_USER_AGENT`, `SCRAPER_RATE_LIMIT_SECONDS` from `.env`.

## Produces

- `ml/ingest.py` → populated `training_data`.
- `scraper/` package → populated `market_listings`.
- A **Gate-1 report** (design + live sample results).

## Part A — Ingest (`ml/ingest.py`)

Load `merc.csv`, clean, convert, write. **Cleaning rules:**

1. `str.strip()` all `model` values; normalise to canonical class names (uppercase-compare, map
   `SL CLASS`/`SL Class` → one canonical label per class). Produce a fixed canonical model set.
2. Drop or quarantine the numeric-only model rows (`230/220/200/180`) — they lack a class; log the
   count dropped (do not silently discard).
3. Sanity filters: `1970 ≤ year ≤ current_year`, `price > 0`, `mileage ≥ 0`, `engineSize ≥ 0`.
4. `age = current_year - year`; `price_rm = round(price_gbp * FX_GBP_TO_RM)`.
5. Idempotent load: truncate+reload or upsert so re-running doesn't duplicate.

Emit a summary: rows in, rows dropped (by reason), rows written, RM price range.

## Part B — Scraper (`scraper/`)

**`base.py` — polite fetcher (shared by both sites):**
- Reads and respects `robots.txt` for each domain before fetching.
- Rate limit `SCRAPER_RATE_LIMIT_SECONDS` between requests + random jitter.
- Exponential backoff on 429/5xx; max retries; per-request timeout.
- On-disk response cache (so re-runs during dev don't re-hit the sites).
- Configurable `User-Agent` with contact info; only public listing pages; **no auth bypass, no
  CAPTCHA circumvention, no protected endpoints.**
- Hard page/listing cap per run (config) to keep the sample small and polite.

**`mudah.py` / `carlist.py` — extractors:**
- Target the public Mercedes-Benz used-car search results + listing pages.
- Paginate up to the configured cap.
- Extract → normalise to `market_listings`: `source, listing_url, model (map to canonical class),
  variant, year, price_rm, mileage, transmission, fuel_type, location, seller_type, posted_at,
  scraped_at`.
- **Mercedes-only filter**; skip non-Mercedes or unparseable rows (log counts).
- Dedup on `listing_url` (UNIQUE) — upsert.

> Selectors are verified live at Gate 1 (marketplace DOMs change). `fixtures/` holds saved sample
> HTML captured during the sample run so unit tests never hit the network.

**`pipeline.py`** orchestrates: fetch → extract → normalise → upsert, with the run summary.

## ⛔ Gate 1 — what I bring to you

1. **Design review:** the selector/field map per site, rate-limit settings, robots outcome, the
   `market_listings` normalisation, and the ToS/robots posture.
2. **Live sample-run report:** counts fetched vs. stored per site, a sample of real rows, and an
   explicit blocked/partial report if a site refuses. **Zero synthetic fills.** You approve before
   any larger run.

## Tests (PyTest — no network)

- Ingest: canonical model mapping, numeric-only rows dropped with correct count, GBP→RM math,
  sanity filters, idempotent reload.
- Extractors: parse saved `fixtures/` pages into exactly-correct normalised rows.
- Base fetcher: honours rate limit (mock clock), backs off on 429 (mock), respects a `Disallow`
  in a mock `robots.txt`, uses cache on second call.
- Mercedes-only filter rejects a non-Mercedes fixture.

## Done criteria

- `python -m ml.ingest` populates `training_data` with the run summary; re-running is idempotent.
- Scraper runs against fixtures in tests with zero network; live run gated behind Gate 1 approval.
- After an approved sample run, `market_listings` holds only real Mercedes listings; every row
  traces to a `listing_url`.
- No synthetic/AI-generated rows anywhere. Connection string never printed by ingest or scraper.
