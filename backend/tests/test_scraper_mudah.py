"""Mudah extractor tests (offline fixtures only)."""

from pathlib import Path

from scraper.mudah import MudahExtractor

FIXTURES = Path(__file__).resolve().parents[1] / "scraper" / "fixtures"


def test_search_results_parse_mercedes_rows():
    html = (FIXTURES / "mudah_search_results.html").read_text(encoding="utf-8")
    rows, summary = MudahExtractor().extract_search_results(html)

    assert summary["fetched"] >= 1
    assert summary["mercedes_kept"] >= 1
    assert all(row["source"] == "mudah" for row in rows)
    assert all(row["listing_url"].startswith("https://www.mudah.my/") for row in rows)
    assert all(row["price_rm"] > 0 for row in rows)


def test_listing_detail_parse():
    html = (FIXTURES / "mudah_listing_detail.html").read_text(encoding="utf-8")
    row = MudahExtractor().extract_listing_detail(html)

    assert row is not None
    assert row["model"] == "C_CLASS"
    assert row["year"] == 2020
    assert row["listing_url"].startswith("https://www.mudah.my/")


def test_non_mercedes_fixture_rejected():
    html = (FIXTURES / "mudah_search_results.html").read_text(encoding="utf-8")
    html = html.replace("Mercedes", "Toyota").replace("mercedes", "toyota")
    rows, summary = MudahExtractor().extract_search_results(html)

    assert rows == []
    assert summary["skipped_non_mercedes"] + summary["skipped_unparseable"] >= 1
