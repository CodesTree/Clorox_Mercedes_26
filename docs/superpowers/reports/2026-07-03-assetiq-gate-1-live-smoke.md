# AssetIQ Gate 1 Report - Data & Scraper Live Smoke

Date: 2026-07-03
Track: Data
Phase: 01 - Data & Scraper
Status: Conditionally approved for controlled live smoke test only

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
PENDING - run the controlled live smoke command above and paste the resulting summary here.
```

