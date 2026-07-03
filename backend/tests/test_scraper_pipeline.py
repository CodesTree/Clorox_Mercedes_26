"""Pipeline integration tests (fixtures only, no network)."""

from pathlib import Path

from app.db import SessionLocal, init_db
from app.orm import MarketListing
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
