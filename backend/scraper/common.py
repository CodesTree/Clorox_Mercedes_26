"""Shared HTML/JSON parsing helpers for marketplace extractors."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

MUDAH_BASE = "https://www.mudah.my"
CARLIST_BASE = "https://www.carlist.my"


def extract_next_data(html: str) -> dict[str, Any]:
    """Parse Mudah __NEXT_DATA__ bootstrap JSON."""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return {}
    return json.loads(tag.string)


def extract_json_ld_blocks(html: str) -> list[Any]:
    """Return all JSON-LD objects embedded in a page."""
    soup = BeautifulSoup(html, "html.parser")
    blocks: list[Any] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        if not tag.string:
            continue
        payload = json.loads(tag.string)
        if isinstance(payload, list):
            blocks.extend(payload)
        else:
            blocks.append(payload)
    return blocks


def pick_first(*values: Any) -> Any:
    """Return the first non-empty value."""
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def parse_price_rm(raw: Any) -> int | None:
    """Normalize RM price strings or numerics to integer Ringgit."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    digits = re.sub(r"[^\d]", "", str(raw))
    if not digits:
        return None
    return int(digits)


def parse_mileage_km(raw: Any) -> int | None:
    """Parse mileage from numeric, string, or Mudah {gte,lte} range dict."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        gte = raw.get("gte")
        lte = raw.get("lte")
        if gte is not None and lte is not None:
            return (int(gte) + int(lte)) // 2
        if gte is not None:
            return int(gte)
        if lte is not None:
            return int(lte)
        return None
    text = str(raw).lower().replace(",", "")
    range_match = re.search(r"(\d+)\s*k?\s*-\s*(\d+)\s*k?", text)
    if range_match:
        low = int(range_match.group(1))
        high = int(range_match.group(2))
        multiplier = 1000 if "k" in text else 1
        return ((low + high) // 2) * multiplier
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    value = int(digits)
    if "k" in text and value < 1000:
        return value * 1000
    return value


def normalize_posted_at(raw: Any) -> str | None:
    """Normalize posted timestamps to ISO-8601 YYYY-MM-DD."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw, tz=timezone.utc).strftime("%Y-%m-%d")
    text = str(raw).strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(text[:19], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    iso_prefix = re.match(r"(\d{4}-\d{2}-\d{2})", text)
    if iso_prefix:
        return iso_prefix.group(1)
    return None


def normalize_transmission(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"auto", "automatic", "at"}:
        return "Automatic"
    if lowered in {"manual", "mt"}:
        return "Manual"
    if "semi" in lowered:
        return "Semi-Auto"
    return text.title()


def normalize_fuel_type(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    return text.title()


def seller_type_from_flags(*, company_ad: Any = None, profile_type: str = "") -> str:
    if profile_type:
        lowered = profile_type.lower()
        if "dealer" in lowered:
            return "dealer"
        if "private" in lowered or "owner" in lowered:
            return "private"
    if company_ad in (True, 1, "1", "true", "True"):
        return "dealer"
    if company_ad in (False, 0, "0", "false", "False"):
        return "private"
    return "unknown"


def absolutize_url(base: str, href: str | None) -> str | None:
    if not href:
        return None
    return urljoin(base, href)


def listing_url_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def meta_content(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": name})
    if tag and tag.get("content"):
        return str(tag["content"]).strip()
    return None
