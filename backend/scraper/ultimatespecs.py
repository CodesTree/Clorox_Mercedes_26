"""UltimateSpecs technical-spec parser and ingester.

This module is deliberately separate from marketplace listings and training
data. Fixture mode is the default test path; live mode only fetches approved
model URLs with the shared polite fetcher.
"""

from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.orm import VehicleSpec
from scraper.export_joined_specs import load_joined_specs_rows, write_joined_specs_csv
from scraper.base import PoliteFetcher, ScraperConfig

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
ULTIMATESPECS_BASE = "https://www.ultimatespecs.com"

# Keep live scope intentionally narrow. --url can be used for one explicitly
# approved detail page, or for this one approved W206 generation seed page.
APPROVED_MODEL_URLS: dict[str, list[str]] = {"c200": []}
APPROVED_GENERATION_URLS = {
    "https://www.ultimatespecs.com/car-specs/Mercedes-Benz/M484/W204-Class-C",
    "https://www.ultimatespecs.com/car-specs/Mercedes-Benz/M3552/C-Class-(W204-2011)-Sedan",
    "https://www.ultimatespecs.com/car-specs/Mercedes-Benz/M7349/W205-Class-C",
    "https://www.ultimatespecs.com/car-specs/Mercedes-Benz/M9956/Class-C-(W205-2019)",
    "https://www.ultimatespecs.com/car-specs/Mercedes-Benz/M11849/Class-C-(W206)"
}
JOINED_EXPORT_PATH = Path("data/snapshots/market_specs_joined_export.csv")

SpecStatus = Literal["ok", "blocked_by_robots", "fetch_failed", "extract_failed", "not_configured"]


@dataclass
class UltimateSpecsSummary:
    status: SpecStatus
    fetched: int = 0
    stored: int = 0
    error: str = ""


SPEC_FIELD_ALIASES = {
    "engine type": "engine_type",
    "engine type - number of cylinders": "engine_type",
    "engine displacement": "engine_cc",
    "engine size": "engine_cc",
    "aspiration": "engine_aspiration",
    "engine aspiration": "engine_aspiration",
    "transmission": "transmission",
    "gearbox": "transmission",
    "transmission gearbox - number of speeds": "transmission",
    "number of gears": "number_of_gears",
    "top speed": "top_speed_kmh",
    "front brakes": "front_brakes",
    "front brakes - disc dimensions": "front_brakes",
    "rear brakes": "rear_brakes",
    "rear brakes - disc dimensions": "rear_brakes",
    "front suspension": "front_suspension",
    "rear suspension": "rear_suspension",
    "trunk / boot capacity": "boot_space_litres",
    "boot capacity": "boot_space_litres",
    "seats": "seat_capacity",
    "number of seats": "seat_capacity",
    "num. of seats": "seat_capacity",
    "doors": "number_of_doors",
    "number of doors": "number_of_doors",
    "num. of doors": "number_of_doors",
    "torque": "torque_nm",
    "maximum torque": "torque_nm",
    "acceleration 0 to 100 km/h": "zero_to_100_kmh_s",
    "acceleration 0 to 100 km/h (0 to 62 mph)": "zero_to_100_kmh_s",
    "0 to 100 km/h": "zero_to_100_kmh_s",
    "fuel type": "fuel_type",
    "fuel": "fuel_type",
}


class UltimateSpecsExtractor:
    source = "ultimatespecs"

    def extract_detail(self, html: str, *, source_url: str) -> dict[str, Any] | None:
        soup = BeautifulSoup(html, "html.parser")
        title = self._clean_text((soup.find("h1") or soup.find("title")).get_text(" ", strip=True))
        if not title or "mercedes" not in title.lower() or "c" not in title.lower():
            return None

        row: dict[str, Any] = {
            "source": self.source,
            "source_url": source_url,
            "make": "Mercedes-Benz",
            "model": "C_CLASS",
            "variant": self._variant_from_title(title),
            "generation": self._generation_from_title(title),
            "year_start": None,
            "year_end": None,
            "specific_model": title,
            "engine_type": None,
            "engine_cc": None,
            "engine_aspiration": None,
            "transmission": None,
            "number_of_gears": None,
            "top_speed_kmh": None,
            "front_brakes": None,
            "rear_brakes": None,
            "front_suspension": None,
            "rear_suspension": None,
            "boot_space_litres": None,
            "seat_capacity": None,
            "number_of_doors": None,
            "torque_nm": None,
            "zero_to_100_kmh_s": None,
            "fuel_type": None,
            "scraped_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }
        page_text = soup.get_text("\n", strip=True)
        self._apply_years(row, f"{title}\n{page_text}")

        for label, value in self._spec_pairs(soup).items():
            field = SPEC_FIELD_ALIASES.get(label)
            if not field:
                continue
            row[field] = self._normalize_field(field, value)
            if field == "transmission" and row["number_of_gears"] is None:
                row["number_of_gears"] = self._first_int(value)

        if not row["variant"]:
            row["variant"] = self._variant_from_title(row["specific_model"])
        return row

    def extract_c200_detail_links(self, html: str, *, source_url: str) -> list[str]:
        """Extract C200-related exact detail links from an approved generation page."""
        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            text = self._clean_text(anchor.get_text(" ", strip=True))
            href = str(anchor["href"])
            haystack = f"{text} {href}".lower()
            if not re.search(r"\bc[\s-]?200\b", haystack):
                continue
            if re.search(
                r"\bc[\s-]?200\s*d\b|[-/]200-d(?:\.|/|$)|\bcdi\b|\bbluetec\b|\bdiesel\b",
                haystack,
            ):
                continue
            absolute = _canonical_url(urljoin(source_url, href))
            if not self._is_ultimatespecs_detail_url(absolute):
                continue
            if absolute not in seen:
                seen.add(absolute)
                links.append(absolute)
        return links

    def _is_ultimatespecs_detail_url(self, url: str) -> bool:
        parsed = urlparse(url)
        return (
            parsed.netloc.lower() == "www.ultimatespecs.com"
            and parsed.path.startswith("/car-specs/Mercedes-Benz/")
        )

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

    def _normalize_field(self, field: str, value: str) -> Any:
        if field in {"engine_cc", "number_of_gears", "top_speed_kmh", "boot_space_litres", "seat_capacity", "number_of_doors", "torque_nm"}:
            return self._first_int(value)
        if field == "zero_to_100_kmh_s":
            return self._first_float(value)
        if field == "transmission":
            return value or None
        if field == "fuel_type":
            return value.title() if value else None
        return value or None

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

    def _variant_from_title(self, title: str) -> str | None:
        compact_match = re.search(r"\bC\s?200(?:\s+4MATIC)?(?:\s+9G-TRONIC)?\b", title, re.I)
        if compact_match:
            return re.sub(r"\s+", " ", compact_match.group(0).upper().replace("C ", "C"))
        sedan_match = re.search(r"\b(?:Sedan|Berlina|Estate)\s+200\b", title, re.I)
        if sedan_match:
            return "C200"
        class_match = re.search(
            r"\bClass\s+C\s+\(W\d{3}\)\s+200(?:\s+4MATIC)?(?:\s+9G-TRONIC)?\b",
            title,
            re.I,
        )
        if not class_match:
            return None
        suffix = re.sub(r"^.*?\)\s+", "", class_match.group(0), flags=re.I)
        return f"C{suffix}".upper()

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


def upsert_vehicle_specs(session: Session, rows: list[dict[str, Any]]) -> int:
    written = 0
    for row in rows:
        existing = session.query(VehicleSpec).filter(VehicleSpec.source_url == row["source_url"]).one_or_none()
        if existing:
            for field, value in row.items():
                if field != "source_url":
                    setattr(existing, field, value)
        else:
            session.add(VehicleSpec(**row))
        written += 1
    session.commit()
    return written


def _build_fetcher() -> PoliteFetcher:
    settings = get_settings()
    return PoliteFetcher(
        ScraperConfig(
            user_agent=settings.scraper_user_agent,
            rate_limit_seconds=settings.scraper_rate_limit_seconds,
            rate_limit_jitter=0.5,
            cache_dir=Path(__file__).parent / "cache" / "ultimatespecs",
            cache_ttl_hours=24,
        )
    )


def _fixture_urls() -> list[tuple[str, str]]:
    path = FIXTURES_DIR / "ultimatespecs_c200_detail.html"
    return [(path.read_text(encoding="utf-8"), f"{ULTIMATESPECS_BASE}/fixture/mercedes-c200")]


def _live_urls(model: str, explicit_url: str | None) -> list[str]:
    if explicit_url:
        return [explicit_url]
    return APPROVED_MODEL_URLS.get(model.lower(), [])


def _canonical_url(url: str) -> str:
    return unquote(urldefrag(url)[0])


def _is_approved_generation_url(url: str) -> bool:
    return _canonical_url(url) in APPROVED_GENERATION_URLS


def run(
    session: Session,
    *,
    use_fixtures: bool,
    use_network: bool,
    model: str = "c200",
    url: str | None = None,
    fetcher: PoliteFetcher | None = None,
) -> UltimateSpecsSummary:
    extractor = UltimateSpecsExtractor()
    html_and_urls: list[tuple[str, str]] = []

    if use_fixtures:
        html_and_urls = _fixture_urls()
    elif use_network:
        urls = _live_urls(model, url)
        if not urls:
            return UltimateSpecsSummary(
                status="not_configured",
                error=f"No approved UltimateSpecs URL configured for model={model}; pass --url for one approved page.",
            )
        fetcher = fetcher or _build_fetcher()
        for target_url in urls:
            try:
                html = fetcher.fetch(target_url)
            except ValueError as exc:
                return UltimateSpecsSummary(status="blocked_by_robots", error=str(exc))
            if not html:
                return UltimateSpecsSummary(status="fetch_failed", error=getattr(fetcher, "last_error", "") or "empty response")
            if _is_approved_generation_url(target_url):
                detail_urls = extractor.extract_c200_detail_links(html, source_url=_canonical_url(target_url))
                if not detail_urls:
                    return UltimateSpecsSummary(
                        status="extract_failed",
                        fetched=1,
                        error=f"No C200 detail links found on {target_url}",
                    )
                for detail_url in detail_urls:
                    try:
                        detail_html = fetcher.fetch(detail_url)
                    except ValueError as exc:
                        return UltimateSpecsSummary(status="blocked_by_robots", fetched=1, error=str(exc))
                    if not detail_html:
                        return UltimateSpecsSummary(
                            status="fetch_failed",
                            fetched=1,
                            error=getattr(fetcher, "last_error", "") or "empty response",
                        )
                    html_and_urls.append((detail_html, detail_url))
            else:
                html_and_urls.append((html, _canonical_url(target_url)))

    rows: list[dict[str, Any]] = []
    for html, source_url in html_and_urls:
        row = extractor.extract_detail(html, source_url=source_url)
        if row is None:
            return UltimateSpecsSummary(status="extract_failed", fetched=len(html_and_urls), error=f"Could not parse {source_url}")
        rows.append(row)

    stored = upsert_vehicle_specs(session, rows)
    return UltimateSpecsSummary(status="ok", fetched=len(rows), stored=stored)


def regenerate_joined_export(session: Session, output_path: Path = JOINED_EXPORT_PATH) -> int:
    rows = load_joined_specs_rows(session)
    write_joined_specs_csv(rows, output_path)
    return len(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="UltimateSpecs Mercedes C200 technical-spec ingest")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixtures", action="store_true", help="Parse saved fixture HTML with no network")
    mode.add_argument("--live", action="store_true", help="Fetch one approved UltimateSpecs page politely")
    parser.add_argument("--model", default="c200", help="Approved model key; currently scoped to c200")
    parser.add_argument("--url", help="One explicitly approved UltimateSpecs detail URL for live mode")
    return parser.parse_args(argv)


def cli(argv: list[str] | None = None) -> UltimateSpecsSummary:
    args = parse_args(argv)
    init_db()
    session = SessionLocal()
    joined_rows = 0
    try:
        summary = run(
            session,
            use_fixtures=bool(args.fixtures),
            use_network=bool(args.live),
            model=args.model,
            url=args.url,
        )
        if summary.status == "ok":
            joined_rows = regenerate_joined_export(session)
    finally:
        session.close()

    print("\n" + "=" * 60)
    print("ULTIMATESPECS INGEST SUMMARY")
    print("=" * 60)
    print(f"Status:  {summary.status}")
    print(f"Fetched: {summary.fetched}")
    print(f"Stored:  {summary.stored}")
    if summary.error:
        print(f"Error:   {summary.error}")
    if summary.status == "ok":
        print(f"Joined export: {JOINED_EXPORT_PATH} ({joined_rows} rows)")
    print("=" * 60 + "\n")
    return summary


if __name__ == "__main__":
    cli()
