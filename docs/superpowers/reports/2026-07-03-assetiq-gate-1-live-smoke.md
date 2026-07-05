# AssetIQ Gate 1 Report - Data & Scraper Live Smoke

Date: 2026-07-03
Track: Data
Phase: 01 - Data & Scraper
Status: Gate 1 live smoke updated - Mudah live OK; Carlist blocked by anti-bot challenge

## Approval Conditions

1. Do not bypass robots.txt.
2. Do not insert synthetic live data.
3. If live sites are blocked by robots.txt, report `blocked_by_robots` as the Gate 1 live outcome.
4. Record test commands, outputs, DB counts, and live-site result in this report.
5. Confirm or patch `Crawl-delay` handling against `SCRAPER_RATE_LIMIT_SECONDS`.

## Local Implementation Evidence

Command:

```powershell
.\venv\Scripts\python.exe -m pytest
```

Output:

```text
45 passed
```

Command:

```powershell
.\venv\Scripts\python.exe -m ml.ingest
```

Output:

```text
Rows in (merc.csv):     13119
Rows dropped (numeric): 4
Rows dropped (sanity):  108
Rows written:           13007
Price RM range:         3,835 - 943,994
```

Command:

```powershell
.\venv\Scripts\python.exe -m scraper.pipeline --fixtures --site all
```

Output:

```text
mode=fixtures
site=all
use_network=False
use_fixtures=True
Mudah status:     ok
Mudah fetched:    1
Mudah stored:     1 (skipped 0)
Carlist status:     ok
Carlist fetched:    1
Carlist stored:     1 (skipped 0)
Total stored:     2
```

DB counts after local verification:

```text
training_data: 13007
market_listings: 2
```

Fixture-derived listing traces:

```text
carlist C_CLASS 2023 228000 https://www.carlist.my/recon-cars/2023-mercedes-benz-c200-1-5-avantgarde-amg-isg-sedan-full-spec-2-memory-seat-panaromic-sunroof-power-boot-hud-360-camera-burmester-system-unreg/19046563
mudah C_CLASS 2020 149000 https://www.mudah.my/2020-mercedes-benz-c200-1-5-4matic-laureus-114758332.htm
```

## Scraper Design Posture

- Live mode is explicit: `scraper.pipeline` requires either `--live` or `--fixtures`.
- Fixture mode uses saved HTML and does not hit the network.
- Live mode uses `PoliteFetcher`, which checks `robots.txt` before fetching.
- `robots.txt` disallow is surfaced as `blocked_by_robots` in the pipeline summary.
- `robots.txt` is fetched with the configured `SCRAPER_USER_AGENT`; 401/403 robots responses fail
  closed, 404 robots responses allow fetch, and parsed `Crawl-delay` is honoured.
- Listings are upserted by unique `listing_url`.
- Extractors reject non-Mercedes rows and unparseable rows.
- Synthetic live listings are not generated or inserted.

## Crawl-delay Handling

`PoliteFetcher` now records `Crawl-delay` from each parsed `robots.txt` and applies:

```text
effective_rate_limit_seconds = max(SCRAPER_RATE_LIMIT_SECONDS, robots_crawl_delay)
```

The delay is domain-specific. If `robots.txt` does not provide `Crawl-delay`, the configured
`SCRAPER_RATE_LIMIT_SECONDS` remains the rate limit.

Regression coverage:

```text
test_crawl_delay_overrides_shorter_config_rate_limit
test_config_rate_limit_overrides_shorter_crawl_delay
```

Latest verification after adding Crawl-delay coverage:

```text
47 passed
```

## Controlled Live Smoke Test

Final command to run from the repository root:

```powershell
Set-Location .\backend
..\venv\Scripts\python.exe -m scraper.pipeline --live --site all
```

Expected outcomes:

- If a site allows the configured public Mercedes search URL, the pipeline stores only parsed real
  Mercedes rows with source `listing_url`.
- If a site is disallowed by `robots.txt`, the pipeline records `blocked_by_robots` for that site.
- If both sites are blocked, the Gate 1 live result is blocked/partial with no synthetic fills.

Live smoke result:

```text
============================================================
SCRAPER PIPELINE SUMMARY
============================================================
mode=live
site=all
use_network=True
use_fixtures=False
Timestamp:        2026-07-03T11:06:17.047129
Mudah status:     blocked_by_robots
Mudah fetched:    0
Mudah stored:     0 (skipped 0)
Mudah error:      robots.txt disallows fetching https://www.mudah.my/malaysia/cars-for-sale/mercedes-benz/c200?q=mercedes+benz+c200
Carlist status:     blocked_by_robots
Carlist fetched:    0
Carlist stored:     0 (skipped 0)
Carlist error:      robots.txt disallows fetching https://www.carlist.my/cars-for-sale/mercedes-benz/c-class/c200/malaysia
Total stored:     0
============================================================
```

Gate 1 outcome:

```text
Both configured live public search URLs were blocked by robots.txt.
No live listings were fetched.
No live listings were stored.
No synthetic rows were inserted.
The blocked_by_robots outcome satisfies the conditional Gate 1 approval path.
```

## Update - Robots User-Agent Fix And New Live Result

The original `blocked_by_robots` result was caused by Python `RobotFileParser.read()` fetching
`robots.txt` with urllib's default User-Agent. Mudah returned HTTP 403 to that default request,
which caused `RobotFileParser` to set `disallow_all=True`. After patching `PoliteFetcher` to fetch
`robots.txt` with the configured `SCRAPER_USER_AGENT`, Mudah's parsed machine rules allowed the
configured Mercedes search URL.

Command:

```powershell
$env:PYTHONPATH="$PWD\backend"; .\venv\Scripts\python.exe -m scraper.pipeline --live --site all
```

Output:

```text
mode=live
site=all
use_network=True
use_fixtures=False
Mudah status:     ok
Mudah fetched:    40
Mudah stored:     40 (skipped 0)
Carlist status:     fetch_failed
Carlist fetched:    0
Carlist stored:     0 (skipped 0)
Carlist error:      empty response
Total stored:     40
```

After concise fetch-error reporting was added, a Carlist-only live smoke reported:

```text
mode=live
site=carlist
use_network=True
use_fixtures=False
Carlist status:     fetch_failed
Carlist fetched:    0
Carlist stored:     0 (skipped 0)
Carlist error:      HTTP 403 anti-bot challenge page
Total stored:     0
```

Updated Gate 1 outcome:

```text
Mudah live scraping succeeded under parsed robots.txt rules and stored real Mercedes rows.
Carlist is not currently blocked by parsed robots.txt, but live fetch returns a Cloudflare
verification/challenge page. No anti-bot or CAPTCHA bypass was attempted.
No synthetic rows were inserted.
```

## Kaggle Carlist Fallback Review

Notebook reviewed:

```text
https://www.kaggle.com/code/tanshihjen/datacollection-beautifulsoup
```

The notebook uses the public Kaggle dataset:

```text
tanshihjen/malaysia-resale-carlist
Title: Malaysia_Resale_Carlist
License: Apache 2.0
Rows: 974
Mercedes/Benz rows: 105
```

Downloaded file:

```text
data/kaggle_malaysia_resale_carlist.zip
```

Dataset columns:

```text
Description, Monthly_Installment, List_Price, Model, Milleage, Gear_Type, Location
```

Assessment:

```text
The Kaggle dataset is useful as a historical external fallback dataset, but it does not include
original Carlist listing URLs. Therefore it should not be inserted into market_listings under the
current Phase 01 done criteria, which require every market row to trace to a listing_url.
```

## Phase 02 Market Feature Handoff

Scraped market rows remain in `market_listings`; they are not merged into `training_data`.
For Phase 02 comparison/calibration work, a projection helper exports `market_listings` into a
training-like feature shape while preserving traceability.

Command:

```powershell
$env:PYTHONPATH="$PWD\backend"; .\venv\Scripts\python.exe -m ml.market_features --output data\market_features_phase02.csv
```

Output:

```text
Rows:                 66
By source:            {'carlist': 25, 'mudah': 41}
Missing engine_size:  66
Missing transmission: 40
Missing fuel_type:    0
Output:               data\market_features_phase02.csv
```

Exported columns:

```text
source, listing_url, model, year, age, mileage, price_rm, transmission, fuel_type,
engine_size, variant, location, seller_type, posted_at, scraped_at
```

Notes:

```text
engine_size is intentionally null for scraped rows because Phase 01 does not store a verified
engine-size field in market_listings. Missing scraped fields remain nullable rather than inferred.
```

## Phase 02 Requested Specs Export

`market_listings` currently stores listing/comparison fields only:

```text
source, listing_url, model, variant, year, price_rm, mileage, transmission, fuel_type,
location, seller_type, posted_at, scraped_at
```

Read-only full-schema export command:

```powershell
$env:PYTHONPATH="$PWD\backend"; .\venv\Scripts\python.exe -m scraper.export_market_specs --output data\snapshots\market_listings_specs_export_full.csv --format full
```

Read-only compact export command:

```powershell
$env:PYTHONPATH="$PWD\backend"; .\venv\Scripts\python.exe -m scraper.export_market_specs --output data\snapshots\market_listings_specs_export_compact.csv --format compact
```

The full export preserves the teammate-requested 20-column schema and keeps unavailable engineering
fields blank/null for machine-readability. The compact export is recommended for human review
because marketplace listings only provide model/year/mileage/price and some fuel/transmission
fields, plus listing traceability fields such as source and listing_url. Detailed engineering specs
such as engine cc, aspiration, brakes, suspension, boot space, torque, and 0-100 km/h time require
a separate approved vehicle-spec source and are not inferred.

## Phase 02 UltimateSpecs Vehicle Specs Extension

Technical vehicle specs are stored separately in `vehicle_specs`; they are not written to
`training_data` or `market_listings`.

Fixture ingest command:

```powershell
$env:PYTHONPATH="$PWD\backend"; .\venv\Scripts\python.exe -m scraper.ultimatespecs --fixtures
```

Live ingest command shape:

```powershell
$env:PYTHONPATH="$PWD\backend"; .\venv\Scripts\python.exe -m scraper.ultimatespecs --live --model c200 --url <approved-ultimatespecs-detail-url>
```

Live mode uses the shared polite fetcher and must stop if robots.txt disallows the page or the
source blocks access. The default `--model c200` path does not scrape broadly; exact UltimateSpecs
detail URLs must be explicitly approved/configured.

Joined full specs export command:

```powershell
$env:PYTHONPATH="$PWD\backend"; .\venv\Scripts\python.exe -m scraper.export_joined_specs --output data\snapshots\market_specs_joined_export.csv
```

The joined export preserves marketplace mileage/price/year/listing URL and only attaches technical
specs when the listing can be matched to an approved spec row by model, variant, and year evidence.
Rows are labelled `exact`, `partial`, or `unmatched` with `match_confidence`.

## Final Phase 01 Closure Status

Phase 01 is ready to close.

Final evidence:

```text
training_data: 13,007 rows from merc.csv ingest
market_listings: 66 rows
  carlist: 25
  mudah: 41
  missing price/year/mileage/listing_url: 0
  duplicate listing_url groups: 0
vehicle_specs: 18 rows
market_specs_full_export.csv: generated
  export rows: 66
  exact matches: 44
  partial matches: 0
  unmatched: 22
latest tests: 78 passed
```

Closure notes:

- ML ingest completed.
- Marketplace scraper completed with a live data snapshot.
- Vehicle specs ingestion is separate from `market_listings` and `training_data`.
- Joined/full market specs export was generated for downstream use.
- Normal backend setup uses `backend/requirements.txt`; it includes SeleniumBase because live
  scraper browser mode imports `seleniumbase.Driver` and uses SeleniumBase UC mode with Chrome.
- W204, W204 2011, and W205 UltimateSpecs C200 petrol specs were added through approved scoped
  generation URLs/seeds.
- W205 2019 facelift specs were not fetched because the approved seed returned a connection reset;
  the failure was documented and not forced.
- No broad or unbounded UltimateSpecs crawl is claimed; only approved scoped URLs/seeds and extracted
  C200 petrol detail URLs were used.
- Scraper/spec ingestion and export paths do not mutate `training_data`.
- No Markdown preview was generated for the final closure artifact.
