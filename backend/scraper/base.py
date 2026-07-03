import hashlib
import logging
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

_UA_LINE_RE = re.compile(r"(?i)^(user-agent:\s*)(\S+)")

def _strip_ua_versions(content: str) -> str:
    lines = []
    for line in content.splitlines():
        match = _UA_LINE_RE.match(line.strip())
        if match:
            prefix, agent = match.groups()
            lines.append(f"{prefix}{agent.split('/')[0]}")
        else:
            lines.append(line)
    return "\n".join(lines)


@dataclass
class ScraperConfig:
    user_agent: str
    rate_limit_seconds: float
    rate_limit_jitter: float
    cache_dir: Path
    cache_ttl_hours: int
    max_retries: int = 3
    request_timeout_seconds: float = 30.0


class PoliteFetcher:
    """Polite page fetcher with robots.txt, rate limiting, cache, and retries."""

    def __init__(
        self,
        config: ScraperConfig,
        *,
        time_fn=time.time,
        sleep_fn=time.sleep,
    ):
        self.config = config
        self._time = time_fn
        self._sleep = sleep_fn
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)
        self.last_request_time = 0.0
        self._robots: dict[str, RobotFileParser] = {}

    def fetch(self, url: str, use_cache: bool = True) -> str:
        """Fetch a URL politely using a real Chromium browser."""
        self._ensure_allowed(url)

        cache_file = self._cache_path(url)
        if use_cache and self._cache_is_fresh(cache_file):
            logger.debug("Cache hit for %s", url)
            return cache_file.read_text(encoding="utf-8")

        self._apply_rate_limit()

        html = self._fetch_with_backoff(url)
        self.last_request_time = self._time()

        if use_cache and html:
            cache_file.write_text(html, encoding="utf-8")

        return html

    def _ensure_allowed(self, url: str) -> None:
        parser = self._robots_for(url)
        if parser and not parser.can_fetch(self.config.user_agent, url):
            raise ValueError(f"robots.txt disallows fetching {url}")

    def _robots_for(self, url: str) -> RobotFileParser | None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        key = parsed.netloc
        if key in self._robots:
            return self._robots[key]

        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            parser.read()
        except Exception:
            logger.debug("Could not read robots.txt for %s", key)
            parser = RobotFileParser()
        self._robots[key] = parser
        return parser

    def load_robots_txt(self, domain: str, content: str) -> None:
        """Load a mock robots.txt body (used in tests)."""
        parser = RobotFileParser()
        parser.parse(_strip_ua_versions(content).splitlines())
        self._robots[domain] = parser

    def _apply_rate_limit(self) -> None:
        elapsed = self._time() - self.last_request_time
        if elapsed < self.config.rate_limit_seconds:
            wait = (self.config.rate_limit_seconds - elapsed) + random.uniform(
                0, self.config.rate_limit_jitter
            )
            self._sleep(wait)

    def _fetch_with_backoff(self, url: str) -> str:
        delay = self.config.rate_limit_seconds
        last_error = ""
        for attempt in range(self.config.max_retries):
            html, status = self._fetch_once(url)
            if html and status < 400:
                return html
            if status in {429, 500, 502, 503, 504}:
                last_error = f"HTTP {status}"
                self._sleep(delay)
                delay *= 2
                continue
            last_error = html or f"HTTP {status}"
            break
        logger.error("Failed to fetch %s: %s", url, last_error)
        return ""

    def _fetch_once(self, url: str) -> tuple[str, int]:
        """Network fetch via Playwright. Returns (html, pseudo-status)."""
        try:
            logger.info("Network fetch (Playwright): %s", url)
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context(
                    user_agent=self.config.user_agent,
                    viewport={"width": 1920, "height": 1080},
                )
                page = context.new_page()
                response = page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                html = page.content()
                browser.close()
                status = response.status if response else 200
                return html, status
        except Exception as exc:
            logger.error("Playwright failed for %s: %s", url, exc)
            return "", 500

    def _cache_path(self, url: str) -> Path:
        cache_filename = f"{hashlib.md5(url.encode()).hexdigest()}.html"
        return self.config.cache_dir / cache_filename

    def _cache_is_fresh(self, cache_file: Path) -> bool:
        if not cache_file.exists():
            return False
        age_hours = (self._time() - cache_file.stat().st_mtime) / 3600
        return age_hours <= self.config.cache_ttl_hours