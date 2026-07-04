"""UltimateSpecs full-brand crawler tests (fixtures only, no network)."""

import csv
import re
from pathlib import Path

from backend.scraper.big_scraper.ultimatespecs import (
    BRAND_MODELS_URL,
    FULL_CSV_COLUMNS,
    UltimateSpecsExtractor,
    append_csv_row,
    crawl_all,
    load_done_urls,
)

FIXTURES = Path(__file__).resolve().parents[1] / "scraper" / "fixtures"


# --------------------------------------------------------------------------- #
# Full-brand crawl (levels 1-4 + CSV resume)                                  #
# --------------------------------------------------------------------------- #
A_CLASS_FAMILY_URL = "https://www.ultimatespecs.com/car-specs/Mercedes-Benz-models/Mercedes-Benz-A-Class"


def test_extract_family_links_dedupes_and_ignores_noise():
    html = (FIXTURES / "ultimatespecs_brand_models.html").read_text(encoding="utf-8")
    links = UltimateSpecsExtractor().extract_family_links(html, source_url=BRAND_MODELS_URL)

    assert links == [
        A_CLASS_FAMILY_URL,
        "https://www.ultimatespecs.com/car-specs/Mercedes-Benz-models/Mercedes-Benz-CLA",
        "https://www.ultimatespecs.com/car-specs/Mercedes-Benz-models/Mercedes-Benz-EQA",
        "https://www.ultimatespecs.com/car-specs/Mercedes-Benz-models/Mercedes-Benz-Sprinter",
    ]


def test_extract_model_cards_carries_generation_heading_and_versions():
    html = (FIXTURES / "ultimatespecs_family_a_class.html").read_text(encoding="utf-8")
    cards = UltimateSpecsExtractor().extract_model_cards(html, source_url=A_CLASS_FAMILY_URL)

    assert len(cards) == 5
    first = cards[0]
    assert first["generation"] == "W177 Facelift (2022 - Present)"
    assert first["title"] == "Class A (W177 2023)"
    assert first["versions"] == 20
    assert first["url"] == "https://www.ultimatespecs.com/car-specs/Mercedes-Benz/M13038/Class-A-(W177-2023)"
    assert cards[-1]["generation"] == "W168 (1997 - 2004)"
    assert cards[-1]["versions"] == 16


def test_extract_version_links_returns_only_numeric_detail_pages():
    html = (FIXTURES / "ultimatespecs_w206_generation.html").read_text(encoding="utf-8")
    links = UltimateSpecsExtractor().extract_version_links(
        html,
        source_url="https://www.ultimatespecs.com/car-specs/Mercedes-Benz/M11849/Class-C-(W206)",
    )

    assert len(links) == 6  # all versions incl. diesel; example.com noise excluded
    assert all(re.search(r"/car-specs/Mercedes-Benz/\d+/.+\.html$", u) for u in links)
    assert all(u.startswith("https://www.ultimatespecs.com/") for u in links)


def test_extract_full_detail_parses_ice_page_like_picture_4():
    html = """
    <html><body>
    <h1>Mercedes Benz A Class (W168) A140 Specs</h1>
    <p>(1997 - 2001) - Technical Specifications for Years 1997, 1998, 1999, 2000, 2001</p>
    <div>Generation : W168</div>
    <div>Body : Hatchback</div>
    <div>Num. of Doors : 5 doors</div>
    <div>Engine type - Number of cylinders : Inline 4</div>
    <div>Engine Code : 166.940</div>
    <div>Fuel type : Petrol</div>
    <div>Fuel System : Bosch MSM</div>
    <div>Engine Alignment : Transverse</div>
    <div>Engine displacement : 1397 cm3 / 85.3 cu-in</div>
    <div>Number of valves : 8 Valves</div>
    <div>Aspiration : naturally-aspirated</div>
    <div>Compression Ratio : 11.0</div>
    <div>Horsepower : 82 PS / 81 HP / 60 kW @ 4800 rpm</div>
    <div>Maximum torque : 130 Nm / 95 lb-ft @ 3800 rpm</div>
    <div>Drive wheels - Traction - Drivetrain : FWD</div>
    <div>Transmission Gearbox - Number of speeds : 5 speed Manual</div>
    <div>Top Speed : 170 km/h / 106 Mph</div>
    <div>Acceleration 0 to 100 km/h (0 to 62 mph) : 12.9 s</div>
    <div>Fuel Consumption - Economy - City : 8 L/100 km</div>
    <div>Fuel Consumption - Economy - Open road : 4.5 L/100 km</div>
    <div>Fuel Consumption - Economy - Combined : 6.4 L/100 km</div>
    <div>Range : 840 Km</div>
    <div>Fuel Tank Capacity : 54 L / 14.3 gallons</div>
    </body></html>
    """
    row = UltimateSpecsExtractor().extract_full_detail(
        html,
        source_url="https://www.ultimatespecs.com/car-specs/Mercedes-Benz/2336/A140.html",
        context={
            "model_family": "A Class",
            "generation": "W168 (1997 - 2004)",
            "model_page_title": "A Class (W168)",
        },
    )

    assert row is not None
    assert set(row) == set(FULL_CSV_COLUMNS)
    assert row["model_family"] == "A Class"
    assert row["generation"] == "W168 (1997 - 2004)"  # context heading wins
    assert row["model_page_title"] == "A Class (W168)"
    assert row["version_name"] == "Mercedes Benz A Class (W168) A140"
    assert row["year_start"] == 1997
    assert row["year_end"] == 2001
    assert row["body"] == "Hatchback"
    assert row["num_doors"] == 5
    assert row["engine_type"] == "Inline 4"
    assert row["engine_code"] == "166.940"
    assert row["fuel_type"] == "Petrol"
    assert row["fuel_system"] == "Bosch MSM"
    assert row["engine_alignment"] == "Transverse"
    assert row["displacement_cc"] == 1397
    assert row["num_valves"] == 8
    assert row["aspiration"] == "naturally-aspirated"
    assert row["compression_ratio"] == 11.0
    assert row["horsepower_hp"] == 81  # prefers the HP figure over PS
    assert row["torque_nm"] == 130
    assert row["drive_wheels"] == "FWD"
    assert row["transmission"] == "5 speed Manual"
    assert row["top_speed_kmh"] == 170
    assert row["accel_0_100_s"] == 12.9
    assert row["consumption_city_l100km"] == 8.0
    assert row["consumption_openroad_l100km"] == 4.5
    assert row["consumption_combined_l100km"] == 6.4
    assert row["range_km"] == 840
    assert row["fuel_tank_l"] == 54.0
    assert row["battery_capacity_kwh"] is None  # EV fields stay blank on ICE pages


def test_extract_full_detail_parses_ev_fixture_battery_and_charging():
    html = (FIXTURES / "ultimatespecs_ev_detail.html").read_text(encoding="utf-8")
    row = UltimateSpecsExtractor().extract_full_detail(
        html,
        source_url="https://www.ultimatespecs.com/car-specs/Mercedes-Benz/9001/EQA-250.html",
    )

    assert row is not None
    assert row["version_name"] == "Mercedes Benz EQA 250 (H243)"
    assert row["generation"] == "H243"  # from the page (no context supplied)
    assert row["year_start"] == 2021
    assert row["year_end"] is None  # "present"
    assert row["body"] == "SUV"
    assert row["num_doors"] == 5
    assert row["engine_type"] == "Electric"
    assert row["fuel_type"] == "Electric"
    assert row["total_electric_power_hp"] == 190
    assert row["total_electric_torque_nm"] == 375
    assert row["num_electric_engines"] == 1
    assert row["electric_engine_type"] == "Asynchronous"
    assert row["front_axle_power_hp"] == 190
    assert row["front_axle_torque_nm"] == 375
    assert row["drive_wheels"] == "FWD"
    assert row["transmission"] == "1 speed Automatic"
    assert row["top_speed_kmh"] == 160
    assert row["accel_0_100_s"] == 8.9
    assert row["range_km"] == 426
    assert row["avg_energy_consumption"] == 17.7
    assert row["battery_type"] == "Lithium-ion"
    assert row["battery_voltage"] == 420.0
    assert row["battery_capacity_kwh"] == 66.5
    assert row["charging_dc"] == "30 min (10-80%)"
    assert row["charging_wallbox"] == "5 h 45 min"
    assert row["charging_ac"] == "21 h"
    assert row["fast_charge_current"] == "100 kW DC"
    assert row["displacement_cc"] is None  # ICE fields stay blank on EV pages


def test_append_csv_row_writes_header_once_and_load_done_urls_reads_back(tmp_path):
    out = tmp_path / "mercedes_specs_ultimate.csv"
    row = {c: None for c in FULL_CSV_COLUMNS}
    append_csv_row(out, {**row, "source_url": "https://x/1.html"})
    append_csv_row(out, {**row, "source_url": "https://x/2.html"})

    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == ",".join(FULL_CSV_COLUMNS)
    assert len(lines) == 3  # header + 2 rows, no duplicate header
    assert load_done_urls(out) == {"https://x/1.html", "https://x/2.html"}
    assert load_done_urls(tmp_path / "missing.csv") == set()


class _CrawlFakeFetcher:
    """Serves fixtures for the 4 crawl levels; records every fetched URL."""

    last_error = ""

    def __init__(self):
        self.urls: list[str] = []
        self.closed = False
        self._brand = (FIXTURES / "ultimatespecs_brand_models.html").read_text(encoding="utf-8")
        self._family = (FIXTURES / "ultimatespecs_family_a_class.html").read_text(encoding="utf-8")
        self._model = (FIXTURES / "ultimatespecs_w206_generation.html").read_text(encoding="utf-8")
        self._detail = (FIXTURES / "ultimatespecs_c200_detail.html").read_text(encoding="utf-8")

    def fetch(self, url: str) -> str:
        self.urls.append(url)
        if url == BRAND_MODELS_URL:
            return self._brand
        if "/Mercedes-Benz-models/" in url:
            return self._family
        if re.search(r"/car-specs/Mercedes-Benz/M\d+/", url):
            return self._model
        if re.search(r"/car-specs/Mercedes-Benz/\d+/.+\.html$", url):
            return self._detail
        raise AssertionError(f"Unexpected fetch: {url}")

    def close(self) -> None:
        self.closed = True


def test_crawl_all_scrapes_details_once_and_resumes(tmp_path):
    out = tmp_path / "mercedes_specs_ultimate.csv"

    first = crawl_all(_CrawlFakeFetcher(), out_path=out, families=["A-Class"])
    assert first.status == "ok"
    assert first.families == 1
    assert first.model_pages == 5  # five cards on the family fixture
    # 6 unique detail URLs; cards 2-5 hit the done-set (6 scraped, 24 skipped)
    assert first.details_scraped == 6
    assert first.details_skipped == 24
    assert first.errors == []

    with out.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    assert rows[0]["model_family"] == "A Class"
    assert rows[0]["generation"] == "W177 Facelift (2022 - Present)"
    assert rows[0]["engine_type"] == "Inline 4"

    # Second run: everything already in the CSV -> nothing scraped.
    second = crawl_all(_CrawlFakeFetcher(), out_path=out, families=["A-Class"])
    assert second.details_scraped == 0
    assert second.details_skipped == 30


def test_crawl_all_respects_max_details_and_closes_fetcher(tmp_path):
    fetcher = _CrawlFakeFetcher()
    summary = crawl_all(
        fetcher,
        out_path=tmp_path / "out.csv",
        families=["A-Class"],
        max_details=3,
    )
    assert summary.details_scraped == 3
    assert fetcher.closed is True


def test_crawl_all_stops_on_robots_disallow(tmp_path):
    class BlockingFetcher:
        def fetch(self, url: str) -> str:
            raise ValueError(f"robots.txt disallows fetching {url}")

    summary = crawl_all(BlockingFetcher(), out_path=tmp_path / "out.csv")
    assert summary.status == "blocked_by_robots"
    assert "robots.txt disallows" in summary.error
    assert summary.details_scraped == 0
