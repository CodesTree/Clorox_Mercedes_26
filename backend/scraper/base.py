import hashlib
import logging
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

logger = logging.getLogger(__name__)

_UA_LINE_RE = re.compile(r"(?i)^(user-agent:\s*)(\S+)")
_WHITESPACE_RE = re.compile(r"\s+")

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


def looks_like_challenge(html: str) -> bool:
    """True when the HTML is an anti-bot interstitial rather than real content."""
    if not html:
        return False
    lower = html.lower()
    return "cloudflare" in lower and ("just a moment" in lower or "verification" in lower)


def looks_like_server_error(html: str) -> bool:
    """True when the HTML is a hosting-provider error page (e.g. disk quota
    exceeded) rather than real content. Distinct from ``looks_like_challenge``:
    this is the target site's own infrastructure failing, not an anti-bot gate."""
    if not html:
        return False
    lower = html.lower()
    return "insufficient storage" in lower or "insufficient free space left in your storage allocation" in lower


@dataclass
class ScraperConfig:
    user_agent: str
    rate_limit_seconds: float
    rate_limit_jitter: float
    cache_dir: Path
    cache_ttl_hours: int
    max_retries: int = 3
    request_timeout_seconds: float = 30.0
    headless: bool = False


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
        self.last_error = ""
        self._robots: dict[str, RobotFileParser] = {}
        self._crawl_delays: dict[str, float] = {}
        self._driver = None

    def fetch(self, url: str, use_cache: bool = True) -> str:
        """Fetch a URL politely using a real Chromium browser."""
        self._ensure_allowed(url)

        cache_file = self._cache_path(url)
        if use_cache and self._cache_is_fresh(cache_file):
            logger.debug("Cache hit for %s", url)
            return cache_file.read_text(encoding="utf-8")

        self._apply_rate_limit(url)

        self.last_error = ""
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

        parser = self._read_robots(parsed.scheme, parsed.netloc)
        self._robots[key] = parser
        self._record_crawl_delay(key, parser)
        return parser

    def _read_robots(self, scheme: str, netloc: str) -> RobotFileParser:
        robots_url = f"{scheme}://{netloc}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        request = Request(robots_url, headers={"User-Agent": self.config.user_agent})
        try:
            with urlopen(request, timeout=self.config.request_timeout_seconds) as response:
                content = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            if exc.code in {401, 403}:
                parser.disallow_all = True
            elif 400 <= exc.code < 500:
                parser.allow_all = True
            else:
                parser.disallow_all = True
            logger.debug("robots.txt fetch for %s returned HTTP %s", netloc, exc.code)
            return parser
        except URLError as exc:
            parser.disallow_all = True
            logger.debug("Could not read robots.txt for %s: %s", netloc, exc)
            return parser

        parser.parse(_strip_ua_versions(content).splitlines())
        return parser

    def load_robots_txt(self, domain: str, content: str) -> None:
        """Load a mock robots.txt body (used in tests)."""
        parser = RobotFileParser()
        parser.parse(_strip_ua_versions(content).splitlines())
        self._robots[domain] = parser
        self._record_crawl_delay(domain, parser)

    def _record_crawl_delay(self, domain: str, parser: RobotFileParser) -> None:
        delay = parser.crawl_delay(self.config.user_agent)
        if delay is None:
            delay = parser.crawl_delay("*")
        if delay is not None:
            self._crawl_delays[domain] = float(delay)

    def _effective_rate_limit_seconds(self, url: str | None = None) -> float:
        rate_limit = self.config.rate_limit_seconds
        if url:
            domain = urlparse(url).netloc
            crawl_delay = self._crawl_delays.get(domain)
            if crawl_delay is not None:
                rate_limit = max(rate_limit, crawl_delay)
        return rate_limit

    def _apply_rate_limit(self, url: str | None = None) -> None:
        rate_limit_seconds = self._effective_rate_limit_seconds(url)
        elapsed = self._time() - self.last_request_time
        if elapsed < rate_limit_seconds:
            wait = (rate_limit_seconds - elapsed) + random.uniform(
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
            last_error = self._summarize_failed_response(html, status)
            break
        self.last_error = last_error
        logger.error("Failed to fetch %s: %s", url, last_error)
        return ""

    def _summarize_failed_response(self, html: str, status: int) -> str:
        if not html:
            return f"HTTP {status}"
        if looks_like_challenge(html):
            return f"HTTP {status} anti-bot challenge page"
        if looks_like_server_error(html):
            return f"HTTP {status} host storage/server error page"
        text = re.sub(r"<[^>]+>", " ", html)
        text = _WHITESPACE_RE.sub(" ", text).strip()
        if len(text) > 200:
            text = f"{text[:200]}..."
        return f"HTTP {status}: {text}"

    # ----------------------------------------------------------------------
    # _fetch_once using SeleniumBase UC mode with a persistent driver.
    # One Chrome instance serves the whole crawl: launching per page costs
    # ~10-15s each and discards the Cloudflare clearance cookie every time.
    # ----------------------------------------------------------------------
    def _get_driver(self):
        if self._driver is None:
            # Imported lazily: parsing-only paths (tests, fixtures) never need
            # a browser, and SeleniumBase pulls in the whole Selenium stack.
            from seleniumbase import Driver

            self._driver = Driver(
                uc=True,                              # undetected-chrome mode
                headless=self.config.headless,
                headless2=self.config.headless,
                browser="chrome",
                agent=self.config.user_agent,
                page_load_strategy="normal",
            )
            self._driver.implicitly_wait(30)
        return self._driver

    def close(self) -> None:
        """Quit the persistent browser (safe to call multiple times)."""
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:  # pragma: no cover - best-effort teardown
                pass
            self._driver = None

    def __enter__(self) -> "PoliteFetcher":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def __del__(self):  # pragma: no cover - defensive teardown
        try:
            self.close()
        except Exception:
            pass

    def _fetch_once(self, url: str) -> tuple[str, int]:
        """Fetch via SeleniumBase UC – handles Cloudflare JS challenges."""
        try:
            logger.info("Network fetch (SeleniumBase UC): %s", url)
            driver = self._get_driver()
            driver.get(url)
            html = driver.page_source
            if looks_like_challenge(html) or looks_like_server_error(html):
                # Give the UC challenge auto-solve (or the host's transient
                # error) a moment, then re-read once before giving up.
                self._sleep(6)
                html = driver.page_source
                if looks_like_challenge(html) or looks_like_server_error(html):
                    return html, 503  # retryable via backoff
            return html, 200
        except Exception as exc:
            logger.error("SeleniumBase fetch failed for %s: %s", url, exc)
            self.close()  # broken session: recreate the driver on next attempt
            return "", 500  # trigger retry
    # ----------------------------------------------------------------------

    def _cache_path(self, url: str) -> Path:
        cache_filename = f"{hashlib.md5(url.encode()).hexdigest()}.html"
        return self.config.cache_dir / cache_filename

    def _cache_is_fresh(self, cache_file: Path) -> bool:
        if not cache_file.exists():
            return False
        age_hours = (self._time() - cache_file.stat().st_mtime) / 3600
        return age_hours <= self.config.cache_ttl_hours
