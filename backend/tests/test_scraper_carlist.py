"""Carlist extractor tests (offline fixtures only)."""
import re
from pathlib import Path

from scraper.carlist import CarlistExtractor

FIXTURES = Path(__file__).resolve().parents[1] / "scraper" / "fixtures"


def test_search_results_parse_mercedes_rows():
    html = (FIXTURES / "carlist_search_results.html").read_text(encoding="utf-8")
    rows, summary = CarlistExtractor().extract_search_results(html)

    assert summary["fetched"] >= 1
    assert summary["mercedes_kept"] >= 1
    assert all(row["source"] == "carlist" for row in rows)
    assert all(row["model"] == "C_CLASS" for row in rows)
    assert all(row["listing_url"].startswith("https://www.carlist.my/") for row in rows)
    assert rows[0]["price_rm"] == 228000
    assert rows[0]["year"] == 2023


def test_listing_detail_parse():
    html = (FIXTURES / "carlist_listing_detail.html").read_text(encoding="utf-8")
    row = CarlistExtractor().extract_listing_detail(html)

    assert row is not None
    assert row["model"] == "C_CLASS"
    assert row["price_rm"] == 228000
    assert row["year"] == 2023
    assert row["listing_url"].endswith("/19046563")
    assert row["seller_type"] == "dealer"


def test_non_mercedes_fixture_rejected():
    html = (FIXTURES / "carlist_search_results.html").read_text(encoding="utf-8")

    # Remove ALL forms of "Mercedes", including hyphenated/space variants, case‑insensitive
    html = re.sub(r'mercedes[-\s]?benz', 'Toyota', html, flags=re.IGNORECASE)
    html = re.sub(r'\bmercedes\b', 'Toyota', html, flags=re.IGNORECASE)

    rows, summary = CarlistExtractor().extract_search_results(html)
    assert rows == []

    assert summary["skipped_non_mercedes"] >= 1
