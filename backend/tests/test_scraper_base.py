"""PoliteFetcher unit tests (mocked clock/network)."""

from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from scraper.base import PoliteFetcher, ScraperConfig


class FakeClock:
    def __init__(self, start: float = 0.0):
        self.now = start
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _fetcher(tmp_path: Path, clock: FakeClock) -> PoliteFetcher:
    return PoliteFetcher(
        ScraperConfig(
            user_agent="TestBot/1.0",
            rate_limit_seconds=2.0,
            rate_limit_jitter=0.0,
            cache_dir=tmp_path,
            cache_ttl_hours=24,
        ),
        time_fn=clock.time,
        sleep_fn=clock.sleep,
    )


def test_rate_limit_waits_between_requests(tmp_path):
    clock = FakeClock()
    fetcher = _fetcher(tmp_path, clock)
    fetcher.last_request_time = 0.0

    fetcher._apply_rate_limit()
    assert clock.slept == [pytest.approx(2.0)]

    # 5 seconds have passed since the last request at 0.0
    clock.now = 5.0
    fetcher.last_request_time = 0.0
    fetcher._apply_rate_limit()
    assert len(clock.slept) == 1


def test_respects_disallow_in_robots_txt(tmp_path):
    fetcher = _fetcher(tmp_path, FakeClock())
    fetcher.load_robots_txt(
        "www.example.com",
        "User-agent: TestBot/1.0\nDisallow: /blocked\n",
    )

    with pytest.raises(ValueError, match="robots.txt disallows"):
        fetcher.fetch("https://www.example.com/blocked/page.html", use_cache=False)


def test_live_robots_fetch_uses_configured_user_agent(tmp_path, monkeypatch):
    fetcher = _fetcher(tmp_path, FakeClock())
    seen_headers = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"User-agent: *\nDisallow:\n"

    def fake_urlopen(request: Request, timeout: float):
        seen_headers["user_agent"] = request.get_header("User-agent")
        seen_headers["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("scraper.base.urlopen", fake_urlopen)

    parser = fetcher._robots_for("https://www.example.com/listing/1")

    assert parser is not None
    assert parser.can_fetch(fetcher.config.user_agent, "https://www.example.com/listing/1")
    assert seen_headers == {"user_agent": "TestBot/1.0", "timeout": 30.0}


def test_robots_403_fails_closed(tmp_path, monkeypatch):
    fetcher = _fetcher(tmp_path, FakeClock())

    def fake_urlopen(request: Request, timeout: float):
        raise HTTPError(request.full_url, 403, "Forbidden", hdrs=None, fp=None)

    monkeypatch.setattr("scraper.base.urlopen", fake_urlopen)

    with pytest.raises(ValueError, match="robots.txt disallows"):
        fetcher.fetch("https://www.example.com/listing/1", use_cache=False)


def test_robots_404_does_not_block_fetch(tmp_path, monkeypatch):
    fetcher = _fetcher(tmp_path, FakeClock())

    def fake_urlopen(request: Request, timeout: float):
        raise HTTPError(request.full_url, 404, "Not Found", hdrs=None, fp=None)

    monkeypatch.setattr("scraper.base.urlopen", fake_urlopen)
    monkeypatch.setattr(fetcher, "_fetch_once", lambda url: ("<html>ok</html>", 200))

    html = fetcher.fetch("https://www.example.com/listing/1", use_cache=False)

    assert html == "<html>ok</html>"


def test_crawl_delay_overrides_shorter_config_rate_limit(tmp_path):
    clock = FakeClock()
    fetcher = _fetcher(tmp_path, clock)
    fetcher.load_robots_txt(
        "www.example.com",
        "User-agent: TestBot\nCrawl-delay: 5\nDisallow:\n",
    )

    fetcher._apply_rate_limit("https://www.example.com/listing/1")

    assert clock.slept == [pytest.approx(5.0)]


def test_config_rate_limit_overrides_shorter_crawl_delay(tmp_path):
    clock = FakeClock()
    fetcher = _fetcher(tmp_path, clock)
    fetcher.load_robots_txt(
        "www.example.com",
        "User-agent: TestBot\nCrawl-delay: 1\nDisallow:\n",
    )

    fetcher._apply_rate_limit("https://www.example.com/listing/1")

    assert clock.slept == [pytest.approx(2.0)]


def test_cache_used_on_second_call(tmp_path, monkeypatch):
    clock = FakeClock()
    fetcher = _fetcher(tmp_path, clock)
    fetcher.load_robots_txt(
        "www.example.com",
        "User-agent: *\nAllow: /\n",
    )
    calls = {"count": 0}

    def fake_fetch_once(url: str):
        calls["count"] += 1
        return "<html>cached</html>", 200

    monkeypatch.setattr(fetcher, "_fetch_once", fake_fetch_once)

    first = fetcher.fetch("https://www.example.com/listing/1", use_cache=True)
    second = fetcher.fetch("https://www.example.com/listing/1", use_cache=True)

    assert first == second == "<html>cached</html>"
    assert calls["count"] == 1


def test_backs_off_on_429(tmp_path, monkeypatch):
    clock = FakeClock()
    fetcher = _fetcher(tmp_path, clock)
    responses = [( "", 429), ("", 429), ("<html>ok</html>", 200) ]
    state = {"idx": 0}

    def fake_fetch_once(url: str):
        html, status = responses[state["idx"]]
        state["idx"] += 1
        return html, status

    monkeypatch.setattr(fetcher, "_fetch_once", fake_fetch_once)
    monkeypatch.setattr(fetcher, "_ensure_allowed", lambda url: None)

    html = fetcher.fetch("https://www.example.com/retry", use_cache=False)
    assert html == "<html>ok</html>"
    assert state["idx"] == 3
    assert clock.slept  # backoff sleeps occurred


def test_failed_response_summary_collapses_cloudflare_challenge(tmp_path):
    fetcher = _fetcher(tmp_path, FakeClock())

    summary = fetcher._summarize_failed_response(
        "<html><head><title>Just a moment...</title></head>"
        "<body>Performance and Security by Cloudflare verification</body></html>",
        403,
    )

    assert summary == "HTTP 403 anti-bot challenge page"


def test_looks_like_challenge_detects_interstitial_only():
    from scraper.base import looks_like_challenge

    challenge = (
        "<html><head><title>Just a moment...</title></head>"
        "<body>Performance and Security by Cloudflare verification</body></html>"
    )
    real_page = "<html><body><h1>Mercedes Benz A Class (W168) A140 Specs</h1></body></html>"

    assert looks_like_challenge(challenge) is True
    assert looks_like_challenge(real_page) is False
    assert looks_like_challenge("") is False


def test_close_is_safe_without_driver_and_idempotent(tmp_path):
    fetcher = _fetcher(tmp_path, FakeClock())
    fetcher.close()  # no driver created yet
    fetcher.close()  # idempotent
    assert fetcher._driver is None


STORAGE_ERROR_HTML = (
    "<html><body><h1>Insufficient Storage</h1>"
    "<p>The method could not be performed on the resource because the server "
    "is unable to store the representation needed to successfully complete "
    "the request. There is insufficient free space left in your storage "
    "allocation.</p></body></html>"
)


def test_looks_like_server_error_detects_storage_quota_page():
    from scraper.base import looks_like_server_error

    real_page = "<html><body><h1>Mercedes Benz A Class (W168) A140 Specs</h1></body></html>"

    assert looks_like_server_error(STORAGE_ERROR_HTML) is True
    assert looks_like_server_error(real_page) is False
    assert looks_like_server_error("") is False


def test_fetch_once_treats_server_error_page_as_retryable(tmp_path):
    fetcher = _fetcher(tmp_path, FakeClock())

    class FakeDriver:
        page_source = STORAGE_ERROR_HTML

        def get(self, url: str) -> None:
            pass

    fetcher._driver = FakeDriver()  # bypasses real seleniumbase driver creation

    html, status = fetcher._fetch_once("https://www.example.com/car-specs/page.html")

    assert status == 503
    assert html == STORAGE_ERROR_HTML
