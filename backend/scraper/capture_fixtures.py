"""Fixture capture script: fetch live sample pages using PoliteFetcher.

This script uses the production scraper/base.py PoliteFetcher to download
a small number of real pages from Mudah.my and Carlist.my for use as test fixtures.
It respects robots.txt, rate-limits, and caches responses — a real smoke test of base.py.

Usage:
  python -m scraper.capture_fixtures

The captured HTML is saved to backend/scraper/fixtures/ for offline testing.
No network calls will be made in tests after this runs once.
"""

import sys
from pathlib import Path

from scraper.base import PoliteFetcher, ScraperConfig


def capture_mudah_fixtures(fetcher: PoliteFetcher, fixture_dir: Path) -> None:
    """Capture Mudah.my search results and listing detail page.

    Args:
        fetcher: PoliteFetcher instance.
        fixture_dir: Directory to save fixtures.

    TODO(Gate1): Replace these URLs with actual live Mudah.my Mercedes search URLs.
    """
    print("\n[fixtures] Capturing Mudah.my pages...")

    # TODO(P01): Update with actual Mudah.my search results URL
    search_url = "https://www.mudah.my/malaysia/cars-for-sale/mercedes-benz/c200?q=mercedes+benz+c200"  # Placeholder
    listing_url = "https://www.mudah.my/2020-mercedes-benz-c200-1-5-4matic-laureus-114758332.htm"  # Placeholder

    print(f"  Search URL: {search_url}")
    print(f"  Listing URL: {listing_url}")

    try:
        # Fetch search results page.
        search_html = fetcher.fetch(search_url, use_cache=True)
        if search_html:
            search_path = fixture_dir / "mudah_search_results.html"
            search_path.write_text(search_html, encoding="utf-8")
            print(f"  ✓ Saved search results: {search_path}")
        else:
            print(f"  ✗ Failed to fetch search results")

        # Fetch listing detail page.
        listing_html = fetcher.fetch(listing_url, use_cache=True)
        if listing_html:
            listing_path = fixture_dir / "mudah_listing_detail.html"
            listing_path.write_text(listing_html, encoding="utf-8")
            print(f"  ✓ Saved listing detail: {listing_path}")
        else:
            print(f"  ✗ Failed to fetch listing detail")

    except ValueError as e:
        print(f"  ✗ robots.txt blocked: {e}")


def capture_carlist_fixtures(fetcher: PoliteFetcher, fixture_dir: Path) -> None:
    """Capture Carlist.my search results and listing detail page.

    Args:
        fetcher: PoliteFetcher instance.
        fixture_dir: Directory to save fixtures.

    TODO(Gate1): Replace these URLs with actual live Carlist.my Mercedes search URLs.
    """
    print("\n[fixtures] Capturing Carlist.my pages...")

    # TODO(P01): Update with actual Carlist.my search results URL
    search_url = "https://www.carlist.my/cars-for-sale/mercedes-benz/c-class/c200/malaysia"  # Placeholder
    listing_url = "https://www.carlist.my/recon-cars/2023-mercedes-benz-c200-1-5-avantgarde-amg-isg-sedan-full-spec-2-memory-seat-panaromic-sunroof-power-boot-hud-360-camera-burmester-system-unreg/19046563"  # Placeholder

    print(f"  Search URL: {search_url}")
    print(f"  Listing URL: {listing_url}")

    try:
        # Fetch search results page.
        search_html = fetcher.fetch(search_url, use_cache=True)
        if search_html:
            search_path = fixture_dir / "carlist_search_results.html"
            search_path.write_text(search_html, encoding="utf-8")
            print(f"  ✓ Saved search results: {search_path}")
        else:
            print(f"  ✗ Failed to fetch search results")

        # Fetch listing detail page.
        listing_html = fetcher.fetch(listing_url, use_cache=True)
        if listing_html:
            listing_path = fixture_dir / "carlist_listing_detail.html"
            listing_path.write_text(listing_html, encoding="utf-8")
            print(f"  ✓ Saved listing detail: {listing_path}")
        else:
            print(f"  ✗ Failed to fetch listing detail")

    except ValueError as e:
        print(f"  ✗ robots.txt blocked: {e}")


def main():
    """Main entry point: capture fixtures using PoliteFetcher."""
    print("=" * 70)
    print("FIXTURE CAPTURE — Real smoke test of base.py PoliteFetcher")
    print("=" * 70)

    # Create fixture directory.
    fixture_dir = Path(__file__).parent / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[fixtures] Output directory: {fixture_dir}")

    # Initialize fetcher (respects robots.txt, rate-limits, caches).
    config = ScraperConfig(
        user_agent="AssetIQResearchBot/0.1 (+research@assetiq.local)",
        rate_limit_seconds=2.0,  # Slightly aggressive for testing, but still polite.
        rate_limit_jitter=0.3,
        cache_dir=Path(__file__).parent / "cache",
        cache_ttl_hours=24,
    )
    fetcher = PoliteFetcher(config)
    print(f"[fixtures] User-Agent: {config.user_agent}")
    print(f"[fixtures] Rate limit: {config.rate_limit_seconds}s ± {config.rate_limit_jitter}")

    # Capture pages (using the fetcher as a real smoke test).
    print("\n" + "-" * 70)
    capture_mudah_fixtures(fetcher, fixture_dir)
    capture_carlist_fixtures(fetcher, fixture_dir)

    print("\n" + "=" * 70)
    print("FIXTURE CAPTURE COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Review captured HTML in backend/scraper/fixtures/")
    print("  2. Extract CSS selectors for scraper/mudah.py and scraper/carlist.py")
    print("  3. Write extractors using the actual DOM structure")
    print("  4. Write tests against the fixtures (zero network)")
    print()


if __name__ == "__main__":
    main()
