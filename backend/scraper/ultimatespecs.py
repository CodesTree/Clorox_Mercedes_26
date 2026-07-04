"""UltimateSpecs full-brand technical-spec crawler.

Full-brand crawl (``--crawl-all``): walks brand -> family -> generation model
-> version detail across every Mercedes-Benz family on the site and appends
each version's full spec row to ``data/external/mercedes_specs_ultimate.csv``.
Resume-safe: already-scraped source_urls found in the CSV are skipped, and the
fetcher's on-disk cache means re-parsing cached pages costs no network calls.
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from app.config import get_settings
from scraper.base import PoliteFetcher, ScraperConfig

logger = logging.getLogger(__name__)

ULTIMATESPECS_BASE = "https://www.ultimatespecs.com"

BRAND_MODELS_URL = f"{ULTIMATESPECS_BASE}/car-specs/Mercedes-Benz-models"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CRAWL_CSV = REPO_ROOT / "data" / "external" / "mercedes_specs_ultimate.csv"

SpecStatus = Literal["ok", "blocked_by_robots", "fetch_failed", "extract_failed", "not_configured"]


@dataclass
class CrawlSummary:
    status: SpecStatus
    families: int = 0
    model_pages: int = 0
    details_scraped: int = 0
    details_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    error: str = ""


# --------------------------------------------------------------------------- #
# Full-brand crawl schema (mercedes_specs_ultimate.csv)                       #
# --------------------------------------------------------------------------- #
FULL_CSV_COLUMNS = [
    # identity / provenance
    "model_family", "generation", "model_page_title", "version_name",
    "year_start", "year_end",
    # body & production details
    "body", "num_doors",
    # engine technical data (ICE; engine_type also holds the EV layout label)
    "engine_type", "engine_code", "fuel_type", "fuel_system", "engine_alignment",
    "displacement_cc", "num_valves", "aspiration", "compression_ratio",
    "horsepower_hp", "torque_nm", "drive_wheels", "transmission",
    # performance
    "top_speed_kmh", "accel_0_100_s",
    # fuel consumption & range (ICE)
    "consumption_city_l100km", "consumption_openroad_l100km",
    "consumption_combined_l100km", "range_km", "fuel_tank_l",
    # EV powertrain
    "total_electric_power_hp", "total_electric_torque_nm", "num_electric_engines",
    "electric_engine_type", "front_axle_power_hp", "front_axle_torque_nm",
    # EV battery / charging
    "avg_energy_consumption", "battery_type", "battery_voltage",
    "battery_capacity_kwh", "charging_dc", "charging_wallbox", "charging_ac",
    "fast_charge_current",
    # provenance tail
    "source_url", "scraped_at",
]

FULL_SPEC_ALIASES = {
    "generation": "generation",
    "body": "body",
    "doors": "num_doors",
    "number of doors": "num_doors",
    "num. of doors": "num_doors",
    "engine type": "engine_type",
    "engine type - number of cylinders": "engine_type",
    "engine code": "engine_code",
    "fuel type": "fuel_type",
    "fuel": "fuel_type",
    "fuel system": "fuel_system",
    "engine alignment": "engine_alignment",
    "engine displacement": "displacement_cc",
    "engine size": "displacement_cc",
    "number of valves": "num_valves",
    "num. of valves": "num_valves",
    "aspiration": "aspiration",
    "engine aspiration": "aspiration",
    "compression ratio": "compression_ratio",
    "horsepower": "horsepower_hp",
    "maximum torque": "torque_nm",
    "torque": "torque_nm",
    "drive wheels - traction - drivetrain": "drive_wheels",
    "drive wheels": "drive_wheels",
    "drive type": "drive_wheels",
    "transmission gearbox - number of speeds": "transmission",
    "transmission": "transmission",
    "gearbox": "transmission",
    "top speed": "top_speed_kmh",
    "acceleration 0 to 100 km/h (0 to 62 mph)": "accel_0_100_s",
    "acceleration 0 to 100 km/h": "accel_0_100_s",
    "0 to 100 km/h": "accel_0_100_s",
    "range": "range_km",
    "fuel tank capacity": "fuel_tank_l",
    "total electric power": "total_electric_power_hp",
    "total maximum power": "total_electric_power_hp",
    "total electric torque": "total_electric_torque_nm",
    "total maximum torque": "total_electric_torque_nm",
    "number of electric engines": "num_electric_engines",
    "num. of electric engines": "num_electric_engines",
    "electric engine type": "electric_engine_type",
    "front axle electric engine power": "front_axle_power_hp",
    "front axle electric engine torque": "front_axle_torque_nm",
    "average energy consumption": "avg_energy_consumption",
    "battery type": "battery_type",
    "battery voltage": "battery_voltage",
    "battery capacity": "battery_capacity_kwh",
    "nominal capacity": "battery_capacity_kwh",
    "fast charge current": "fast_charge_current",
}

# Fields parsed to numbers; everything else stays a cleaned string.
_HP_INT_FIELDS = {"horsepower_hp", "total_electric_power_hp", "front_axle_power_hp"}
_NM_INT_FIELDS = {"torque_nm", "total_electric_torque_nm", "front_axle_torque_nm"}
_PLAIN_INT_FIELDS = {
    "displacement_cc", "num_valves", "num_doors", "top_speed_kmh",
    "range_km", "num_electric_engines",
}
_FLOAT_FIELDS = {
    "compression_ratio", "accel_0_100_s", "consumption_city_l100km",
    "consumption_openroad_l100km", "consumption_combined_l100km", "fuel_tank_l",
    "battery_capacity_kwh", "avg_energy_consumption", "battery_voltage",
}

_FAMILY_HREF_RE = re.compile(r"/car-specs/Mercedes-Benz-models/Mercedes-Benz-[^/]+/?$")
_MODEL_CARD_HREF_RE = re.compile(r"/car-specs/Mercedes-Benz/M\d+/[^/]+/?$")
_DETAIL_HREF_RE = re.compile(r"/car-specs/Mercedes-Benz/\d+/[^/]+\.html$")


class UltimateSpecsExtractor:
    source = "ultimatespecs"

    # ------------------------------------------------------------------ #
    # Full-brand crawl extractors (levels 1-3)                            #
    # ------------------------------------------------------------------ #
    def extract_family_links(self, html: str, *, source_url: str) -> list[str]:
        """Level 1: model-family links on the Mercedes-Benz-models brand page."""
        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            absolute = _canonical_url(urljoin(source_url, str(anchor["href"])))
            parsed = urlparse(absolute)
            if parsed.netloc.lower() != "www.ultimatespecs.com":
                continue
            if not _FAMILY_HREF_RE.search(parsed.path):
                continue
            if absolute not in seen:
                seen.add(absolute)
                links.append(absolute)
        return links

    def extract_model_cards(self, html: str, *, source_url: str) -> list[dict[str, Any]]:
        """Level 2: generation model cards on a family page.

        Walks the document in order, tracking the most recent heading so each
        card carries its generation label (e.g. "W177 (2018 - 2022)").
        """
        soup = BeautifulSoup(html, "html.parser")
        cards: list[dict[str, Any]] = []
        seen: set[str] = set()
        current_heading: str | None = None
        for element in soup.find_all(["h1", "h2", "h3", "h4", "a"]):
            if element.name != "a":
                text = self._clean_text(element.get_text(" ", strip=True))
                if text:
                    current_heading = text
                continue
            href = element.get("href")
            if not href:
                continue
            absolute = _canonical_url(urljoin(source_url, str(href)))
            parsed = urlparse(absolute)
            if parsed.netloc.lower() != "www.ultimatespecs.com":
                continue
            if not _MODEL_CARD_HREF_RE.search(parsed.path):
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            card_text = self._clean_text(element.get_text(" ", strip=True))
            versions_match = re.search(r"(\d+)\s+Versions?", card_text, re.I)
            cards.append(
                {
                    "generation": current_heading,
                    "title": re.sub(r"\s*\d+\s+Versions?\s*$", "", card_text, flags=re.I) or None,
                    "versions": int(versions_match.group(1)) if versions_match else None,
                    "url": absolute,
                }
            )
        return cards

    def extract_version_links(self, html: str, *, source_url: str) -> list[str]:
        """Level 3: version detail links (.../<numeric-id>/<slug>.html) on a model page."""
        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            absolute = _canonical_url(urljoin(source_url, str(anchor["href"])))
            parsed = urlparse(absolute)
            if parsed.netloc.lower() != "www.ultimatespecs.com":
                continue
            if not _DETAIL_HREF_RE.search(parsed.path):
                continue
            if absolute not in seen:
                seen.add(absolute)
                links.append(absolute)
        return links

    # ------------------------------------------------------------------ #
    # Full-field detail extraction (level 4)                              #
    # ------------------------------------------------------------------ #
    def extract_full_detail(
        self,
        html: str,
        *,
        source_url: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Parse one version detail page into the wide mercedes_specs_ultimate row."""
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("h1") or soup.find("title")
        if title_tag is None:
            return None
        title = self._clean_text(title_tag.get_text(" ", strip=True))
        if not title or "mercedes" not in title.lower():
            return None
        context = context or {}

        row: dict[str, Any] = {column: None for column in FULL_CSV_COLUMNS}
        row["source_url"] = source_url
        row["scraped_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        row["model_family"] = context.get("model_family")
        row["model_page_title"] = context.get("model_page_title")
        row["version_name"] = re.sub(r"\s+Specs$", "", title, flags=re.I)

        page_text = soup.get_text("\n", strip=True)
        self._apply_years(row, f"{title}\n{page_text}")

        for label, value in self._spec_pairs(soup).items():
            field_name = FULL_SPEC_ALIASES.get(label) or self._fuzzy_full_field(label)
            if not field_name:
                continue
            parsed_value = self._normalize_full_field(field_name, value)
            if parsed_value is not None and row.get(field_name) is None:
                row[field_name] = parsed_value

        # Generation priority: family-page heading > detail-page value > title code.
        if context.get("generation"):
            row["generation"] = context["generation"]
        elif not row["generation"]:
            row["generation"] = self._generation_from_title(title)
        return row

    def _fuzzy_full_field(self, label: str) -> str | None:
        """Map label variants the exact alias table misses (NEDC/WLTP suffixes, charging)."""
        if "charging time" in label or "charging" in label:
            if "dc" in label or "fast" in label:
                return "charging_dc"
            if "wallbox" in label or "wall box" in label:
                return "charging_wallbox"
            if "ac" in label:
                return "charging_ac"
            return None
        if "fast charge" in label:
            return "fast_charge_current"
        if "fuel consumption" in label or "economy" in label:
            if "city" in label or "urban" in label and "extra" not in label:
                return "consumption_city_l100km"
            if "open road" in label or "highway" in label or "extra urban" in label:
                return "consumption_openroad_l100km"
            if "combined" in label:
                return "consumption_combined_l100km"
        return None

    def _normalize_full_field(self, field_name: str, value: str) -> Any:
        value = self._clean_text(value)
        if not value or value in {"-", "n/a", "N/A"}:
            return None
        if field_name in _HP_INT_FIELDS:
            match = re.search(r"(\d[\d,]*)\s*HP\b", value, re.I)
            return int(match.group(1).replace(",", "")) if match else self._first_int(value)
        if field_name in _NM_INT_FIELDS:
            match = re.search(r"(\d[\d,]*)\s*Nm\b", value, re.I)
            return int(match.group(1).replace(",", "")) if match else self._first_int(value)
        if field_name in _PLAIN_INT_FIELDS:
            return self._first_int(value)
        if field_name in _FLOAT_FIELDS:
            return self._first_float(value)
        if field_name == "fuel_type":
            return value.title()
        return value

    def _spec_pairs(self, soup: BeautifulSoup) -> dict[str, str]:
        pairs: dict[str, str] = {}
        for table in soup.find_all("table"):
            for tr in table.find_all("tr"):
                cells = [self._clean_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]
                if len(cells) >= 2:
                    pairs[self._normalize_label(cells[0])] = cells[1]

        for container in soup.select(".spec, .spec-row, li"):
            label_tag = container.find(["span", "strong", "b"])
            if not label_tag:
                continue
            label = self._normalize_label(label_tag.get_text(" ", strip=True))
            value = self._clean_text(container.get_text(" ", strip=True).replace(label_tag.get_text(" ", strip=True), "", 1))
            if label and value:
                pairs[label] = value.lstrip(":").strip()
        pairs.update(self._line_pairs(soup))
        return pairs

    def _line_pairs(self, soup: BeautifulSoup) -> dict[str, str]:
        pairs: dict[str, str] = {}
        lines = [
            self._clean_text(line)
            for line in soup.get_text("\n", strip=True).splitlines()
            if self._clean_text(line)
        ]
        for index, line in enumerate(lines):
            if ":" not in line:
                continue
            label_raw, value_raw = line.split(":", 1)
            label = self._normalize_label(label_raw)
            value = self._clean_text(value_raw)
            if not value and index + 1 < len(lines):
                value = lines[index + 1]
            if label and value:
                pairs[label] = value
        return pairs

    def _apply_years(self, row: dict[str, Any], title: str) -> None:
        range_match = re.search(
            r"\((20\d{2}|19\d{2})\s*-\s*((?:20|19)\d{2}|present)\)",
            title,
            re.I,
        )
        if range_match:
            row["year_start"] = int(range_match.group(1))
            row["year_end"] = (
                None if range_match.group(2).lower() == "present" else int(range_match.group(2))
            )
            return

        specs_years_match = re.search(
            r"Technical Specifications for Years\s+((?:19|20)\d{2}(?:,\s*(?:19|20)\d{2})*)",
            title,
            re.I,
        )
        if specs_years_match:
            years = [int(year) for year in re.findall(r"(?:19|20)\d{2}", specs_years_match.group(1))]
            row["year_start"] = min(years)
            row["year_end"] = max(years)
            return

        first_line = title.splitlines()[0] if title else ""
        years = [int(match.group(0)) for match in re.finditer(r"\b(19|20)\d{2}\b", first_line)]
        if len(years) >= 2:
            row["year_start"] = years[0]
            row["year_end"] = years[1]
        elif len(years) == 1:
            row["year_start"] = years[0]
            row["year_end"] = years[0]
        self._apply_generation_year_fallback(row, title)

    def _apply_generation_year_fallback(self, row: dict[str, Any], title: str) -> None:
        lowered = title.lower()
        if "w204 2011" in lowered:
            row["year_start"] = 2011
            row["year_end"] = 2014
            return
        if row["year_start"] is not None and row["year_end"] is not None:
            return
        if "w204" in lowered:
            row["year_start"] = 2007
            row["year_end"] = 2011
        elif "w205 2019" in lowered:
            row["year_start"] = 2018
            row["year_end"] = 2021
        elif "w205" in lowered:
            row["year_start"] = 2014
            row["year_end"] = 2018

    def _generation_from_title(self, title: str) -> str | None:
        match = re.search(r"\bW\d{3}\b", title, re.I)
        return match.group(0).upper() if match else None

    def _normalize_label(self, text: str) -> str:
        return self._clean_text(text).rstrip(":").lower()

    def _clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    def _first_int(self, value: str) -> int | None:
        match = re.search(r"\d[\d,]*", value or "")
        return int(match.group(0).replace(",", "")) if match else None

    def _first_float(self, value: str) -> float | None:
        match = re.search(r"\d+(?:\.\d+)?", value or "")
        return float(match.group(0)) if match else None


def _build_fetcher(headless: bool = False) -> PoliteFetcher:
    settings = get_settings()
    return PoliteFetcher(
        ScraperConfig(
            user_agent=settings.scraper_user_agent,
            rate_limit_seconds=settings.scraper_rate_limit_seconds,
            rate_limit_jitter=0.5,
            cache_dir=Path(__file__).parent / "cache" / "ultimatespecs",
            # 7 days: a multi-day resumed crawl re-parses from cache, no re-fetch.
            cache_ttl_hours=168,
            headless=headless,
        )
    )


def _canonical_url(url: str) -> str:
    return unquote(urldefrag(url)[0])


# --------------------------------------------------------------------------- #
# Full-brand crawl (brand -> family -> model -> version detail -> CSV)        #
# --------------------------------------------------------------------------- #
def load_done_urls(csv_path: Path) -> set[str]:
    """source_urls already present in the output CSV (resume support)."""
    if not csv_path.exists():
        return set()
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return {r["source_url"] for r in csv.DictReader(handle) if r.get("source_url")}


def append_csv_row(csv_path: Path, row: dict[str, Any]) -> None:
    """Append one row, writing the header only when the file is new/empty."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not csv_path.exists() or csv_path.stat().st_size == 0
    with csv_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FULL_CSV_COLUMNS, extrasaction="ignore")
        if needs_header:
            writer.writeheader()
        writer.writerow(row)


def _family_name_from_url(url: str) -> str:
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    return slug.removeprefix("Mercedes-Benz-").replace("-", " ")


class _RobotsBlocked(Exception):
    pass


def crawl_all(
    fetcher: PoliteFetcher,
    *,
    out_path: Path = DEFAULT_CRAWL_CSV,
    families: list[str] | None = None,
    max_details: int | None = None,
    extractor: UltimateSpecsExtractor | None = None,
    log_every: int = 25,
) -> CrawlSummary:
    """Crawl every Mercedes family -> generation model -> version detail to CSV.

    Politeness is enforced by the fetcher (robots.txt, rate limit, cache). A
    robots disallow aborts the whole crawl; any other single-page failure is
    logged into ``summary.errors`` and the crawl continues.
    """
    extractor = extractor or UltimateSpecsExtractor()
    summary = CrawlSummary(status="ok")
    done = load_done_urls(out_path)
    logger.info("crawl_all: %d rows already in %s", len(done), out_path)

    def fetch(url: str) -> str:
        try:
            return fetcher.fetch(url)
        except ValueError as exc:  # robots.txt disallow — stop everything
            raise _RobotsBlocked(str(exc)) from exc

    try:
        brand_html = fetch(BRAND_MODELS_URL)
        if not brand_html:
            return CrawlSummary(status="fetch_failed", error=getattr(fetcher, "last_error", "") or "empty brand page")

        family_urls = extractor.extract_family_links(brand_html, source_url=BRAND_MODELS_URL)
        if not family_urls:
            return CrawlSummary(status="extract_failed", error="no family links found on brand page")
        if families:
            # Hyphen-insensitive substring match: "A-Class" matches "A Class".
            wanted = [f.strip().lower().replace("-", " ") for f in families if f.strip()]
            family_urls = [
                u for u in family_urls
                if any(w in _family_name_from_url(u).lower() for w in wanted)
            ]
            if not family_urls:
                return CrawlSummary(
                    status="extract_failed",
                    error=f"--families filter {families} matched none of the site's families",
                )

        for family_url in family_urls:
            family_name = _family_name_from_url(family_url)
            family_html = fetch(family_url)
            if not family_html:
                summary.errors.append(f"family fetch failed: {family_url}")
                continue
            summary.families += 1

            for card in extractor.extract_model_cards(family_html, source_url=family_url):
                model_html = fetch(card["url"])
                if not model_html:
                    summary.errors.append(f"model fetch failed: {card['url']}")
                    continue
                summary.model_pages += 1
                context = {
                    "model_family": family_name,
                    "generation": card.get("generation"),
                    "model_page_title": card.get("title"),
                }

                for detail_url in extractor.extract_version_links(model_html, source_url=card["url"]):
                    if detail_url in done:
                        summary.details_skipped += 1
                        continue
                    if max_details is not None and summary.details_scraped >= max_details:
                        logger.info("crawl_all: reached --max-details=%d, stopping", max_details)
                        return summary
                    detail_html = fetch(detail_url)
                    if not detail_html:
                        summary.errors.append(f"detail fetch failed: {detail_url}")
                        continue
                    row = extractor.extract_full_detail(
                        detail_html, source_url=detail_url, context=context
                    )
                    if row is None:
                        summary.errors.append(f"detail parse failed: {detail_url}")
                        continue
                    append_csv_row(out_path, row)
                    done.add(detail_url)
                    summary.details_scraped += 1
                    if summary.details_scraped % log_every == 0:
                        logger.info(
                            "crawl_all: %d scraped / %d skipped (family=%s)",
                            summary.details_scraped, summary.details_skipped, family_name,
                        )
    except _RobotsBlocked as exc:
        summary.status = "blocked_by_robots"
        summary.error = str(exc)
    finally:
        close = getattr(fetcher, "close", None)
        if callable(close):
            close()
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl every Mercedes-Benz family -> generation -> version on "
        "UltimateSpecs into a single specs CSV"
    )
    parser.add_argument(
        "--families",
        help='Comma-separated family filter (substring match, e.g. "A-Class,C-Class")',
    )
    parser.add_argument(
        "--max-details",
        type=int,
        help="Stop after scraping this many new detail pages (pilot cap)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_CRAWL_CSV,
        help=f"Output CSV (default: {DEFAULT_CRAWL_CSV})",
    )
    parser.add_argument("--headless", action="store_true", help="Run the browser headless")
    return parser.parse_args(argv)


def cli(argv: list[str] | None = None) -> CrawlSummary:
    args = parse_args(argv)
    families = [f for f in (args.families or "").split(",") if f.strip()] or None
    fetcher = _build_fetcher(headless=bool(args.headless))
    summary = crawl_all(
        fetcher,
        out_path=args.out,
        families=families,
        max_details=args.max_details,
    )
    print("\n" + "=" * 60)
    print("ULTIMATESPECS FULL CRAWL SUMMARY")
    print("=" * 60)
    print(f"Status:           {summary.status}")
    print(f"Families:         {summary.families}")
    print(f"Model pages:      {summary.model_pages}")
    print(f"Details scraped:  {summary.details_scraped}")
    print(f"Details skipped:  {summary.details_skipped} (already in CSV)")
    print(f"Errors:           {len(summary.errors)}")
    for err in summary.errors[:10]:
        print(f"  - {err}")
    if len(summary.errors) > 10:
        print(f"  ... and {len(summary.errors) - 10} more")
    if summary.error:
        print(f"Fatal error:      {summary.error}")
    print(f"Output CSV:       {args.out}")
    print("=" * 60 + "\n")
    return summary


if __name__ == "__main__":
    cli()
