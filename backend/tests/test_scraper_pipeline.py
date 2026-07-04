"""Pipeline integration tests (fixtures only, no network)."""

from pathlib import Path

import pytest

from app.db import SessionLocal, init_db
from app.orm import MarketListing
from scraper import pipeline
from scraper.pipeline import PipelineConfig, run_pipeline

FIXTURES = Path(__file__).resolve().parents[1] / "scraper" / "fixtures"


def test_pipeline_upserts_from_fixtures():
    assert (FIXTURES / "mudah_search_results.html").exists()
    assert (FIXTURES / "carlist_search_results.html").exists()

    init_db()
    session = SessionLocal()
    try:
        summary = run_pipeline(
            session,
            config=PipelineConfig(use_fixtures=True, use_network=False, max_listings_per_run=50),
        )
        count_after_first = session.query(MarketListing).count()

        summary_second = run_pipeline(
            session,
            config=PipelineConfig(use_fixtures=True, use_network=False, max_listings_per_run=50),
        )
        count_after_second = session.query(MarketListing).count()
        row = session.query(MarketListing).first()
    finally:
        session.close()

    assert summary["total_stored"] > 0
    assert summary["carlist_stored"] > 0
    assert count_after_first == count_after_second
    assert summary_second["total_stored"] > 0
    assert row is not None
    assert row.listing_url
    assert row.model


def test_pipeline_reports_robots_block_and_continues_to_next_site():
    class BlockingMudahFetcher:
        def fetch(self, url: str) -> str:
            if "mudah.my" in url:
                raise ValueError(f"robots.txt disallows fetching {url}")
            return (FIXTURES / "carlist_search_results.html").read_text(encoding="utf-8")

    init_db()
    session = SessionLocal()
    try:
        summary = run_pipeline(
            session,
            config=PipelineConfig(use_fixtures=False, use_network=True, max_listings_per_run=50),
            fetcher=BlockingMudahFetcher(),
        )
    finally:
        session.close()

    assert summary["mudah_status"] == "blocked_by_robots"
    assert summary["mudah_fetched"] == 0
    assert summary["mudah_stored"] == 0
    assert "robots.txt disallows" in summary["mudah_error"]
    assert summary["carlist_status"] == "ok"
    assert summary["carlist_fetched"] > 0
    assert summary["carlist_stored"] > 0


def test_pipeline_site_selector_runs_only_requested_site():
    class CarlistOnlyFetcher:
        def fetch(self, url: str) -> str:
            assert "mudah.my" not in url
            return (FIXTURES / "carlist_search_results.html").read_text(encoding="utf-8")

    init_db()
    session = SessionLocal()
    try:
        summary = run_pipeline(
            session,
            config=PipelineConfig(
                use_fixtures=False,
                use_network=True,
                max_listings_per_run=50,
                site="carlist",
            ),
            fetcher=CarlistOnlyFetcher(),
        )
    finally:
        session.close()

    assert summary["mudah_fetched"] == 0
    assert summary["mudah_stored"] == 0
    assert summary["carlist_status"] == "ok"
    assert summary["carlist_stored"] > 0


def test_pipeline_reports_fetcher_last_error_for_empty_response():
    class EmptyCarlistFetcher:
        last_error = "HTTP 403 anti-bot challenge page"

        def fetch(self, url: str) -> str:
            assert "carlist.my" in url
            return ""

    init_db()
    session = SessionLocal()
    try:
        summary = run_pipeline(
            session,
            config=PipelineConfig(use_fixtures=False, use_network=True, site="carlist"),
            fetcher=EmptyCarlistFetcher(),
        )
    finally:
        session.close()

    assert summary["carlist_status"] == "fetch_failed"
    assert summary["carlist_error"] == "HTTP 403 anti-bot challenge page"


def test_cli_parse_requires_explicit_mode():
    with pytest.raises(SystemExit):
        pipeline.parse_args(["--site", "all"])


def test_cli_parse_rejects_live_and_fixtures_together():
    with pytest.raises(SystemExit):
        pipeline.parse_args(["--live", "--fixtures"])


def test_cli_parse_mode_and_site():
    args = pipeline.parse_args(["--live", "--site", "carlist"])

    assert args.live is True
    assert args.fixtures is False
    assert args.site == "carlist"


def test_cli_resolves_mode_selection(monkeypatch):
    calls = []

    def fake_main(*, use_fixtures: bool, use_network: bool, site: str):
        calls.append((use_fixtures, use_network, site))
        return {}

    monkeypatch.setattr(pipeline, "main", fake_main)

    pipeline.cli(["--fixtures", "--site", "mudah"])

    assert calls == [(True, False, "mudah")]
