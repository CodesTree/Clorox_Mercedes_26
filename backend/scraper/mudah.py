"""Mudah.my Mercedes listing extractor.

Field map (verified against fixtures captured 2026-07):
- Search results: ``__NEXT_DATA__ → props.initialState.adListing.byID[*].attributes``
  - price, fueltype, mileage {gte,lte}, listId, subareaName, regionName
  - subject, make/model names, manufactured_year, transmission, listTs/adDate
  - companyAd, url/adview_url for listing path
- Listing detail: ``__NEXT_DATA__ → props.initialState.adDetails.byID[*]`` (same attributes)
  - HTML fallback: icon row under ad_view for year, transmission, mileage band, location
- Canonical search URL:
  https://www.mudah.my/malaysia/cars-for-sale/mercedes-benz/c200?q=mercedes+benz+c200
"""

from __future__ import annotations

import logging
from pydoc import html
import re
from datetime import datetime, timezone
from typing import Any, TypedDict

from bs4 import BeautifulSoup

from ml.constants import is_mercedes, normalize_scraped_class
from scraper.common import (
    MUDAH_BASE,
    absolutize_url,
    extract_next_data,
    normalize_fuel_type,
    normalize_posted_at,
    normalize_transmission,
    parse_mileage_km,
    parse_price_rm,
    pick_first,
    seller_type_from_flags,
)

logger = logging.getLogger(__name__)

SEARCH_URL = (
    "https://www.mudah.my/malaysia/cars-for-sale/mercedes-benz/c200"
    "?q=mercedes+benz+c200"
)


class ExtractSummary(TypedDict):
    fetched: int
    mercedes_kept: int
    skipped_non_mercedes: int
    skipped_unparseable: int


class MudahExtractor:
    """Parse Mudah HTML (live or fixture) into normalised listing dicts."""

    source = "mudah"

    def extract_search_results(self, html: str) -> tuple[list[dict], ExtractSummary]:
        data = extract_next_data(html)
        by_id = (
            data.get("props", {})
            .get("initialState", {})
            .get("adListing", {})
            .get("byID", {})
        )
        rows: list[dict] = []
        summary = ExtractSummary(
            fetched=len(by_id),
            mercedes_kept=0,
            skipped_non_mercedes=0,
            skipped_unparseable=0,
        )
        for listing_id, payload in by_id.items():
            row = self._normalize_payload(
                payload, fallback_list_id=str(listing_id), html=html
            )
            if row is None:
                summary["skipped_unparseable"] += 1
                continue
            if not is_mercedes(make=row.get("_make", ""), title=row.get("_title", "")):
                summary["skipped_non_mercedes"] += 1
                continue
            canonical = normalize_scraped_class(
                row["_title"],
                model_group=row.get("_model_group", ""),
                make=row.get("_make", ""),
            )
            if canonical is None:
                summary["skipped_unparseable"] += 1
                continue
            row["model"] = canonical
            for key in ("_make", "_title", "_model_group"):
                row.pop(key, None)
            rows.append(row)
            summary["mercedes_kept"] += 1
        return rows, summary

    def extract_listing_detail(self, html: str) -> dict | None:
        data = extract_next_data(html)
        state = data.get("props", {}).get("initialState", {})
        by_id = state.get("adDetails", {}).get("byID") or state.get("adListing", {}).get(
            "byID", {}
        )
        if by_id:
            payload = next(iter(by_id.values()))
            row = self._normalize_payload(payload, fallback_list_id=str(payload.get("id") or ""), html=html)
            if row and is_mercedes(make=row.get("_make", ""), title=row.get("_title", "")):
                canonical = normalize_scraped_class(
                    row["_title"],
                    model_group=row.get("_model_group", ""),
                    make=row.get("_make", ""),
                )
                if canonical:
                    row["model"] = canonical
                    for key in ("_make", "_title", "_model_group"):
                        row.pop(key, None)
                    return row

        return self._extract_detail_from_html(html)

    def _normalize_payload(
        self,
        payload: dict[str, Any],
        fallback_list_id: str | None = None,
        html: str = "",
    ) -> dict | None:
        attrs = payload.get("attributes", payload)
        if not isinstance(attrs, dict):
            return None

        list_id = str(pick_first(attrs.get("listId"), fallback_list_id) or "")

        title = pick_first(
            attrs.get("subject"),
            attrs.get("adTitle"),
            attrs.get("title"),
            payload.get("subject"),
        )
        if not title and html and list_id:
            title = self._title_from_html(html, list_id)

        make = pick_first(attrs.get("makeName"), attrs.get("make"), attrs.get("brandName"))
        model_name = pick_first(attrs.get("modelName"), attrs.get("model"))
        model_group = pick_first(attrs.get("categoryName"), attrs.get("familyName"))

        year_raw = pick_first(
            attrs.get("manufacturedYear"),
            attrs.get("manufactured_year"),
            attrs.get("mfgYear"),
            attrs.get("year"),
        )
        try:
            year = int(str(year_raw)[:4]) if year_raw is not None else None
        except (TypeError, ValueError):
            year = None
        if year is None and title:
            year_match = re.search(r"\b(19|20)\d{2}\b", str(title))
            if year_match:
                year = int(year_match.group(0))

        price_rm = parse_price_rm(attrs.get("price"))
        if price_rm is None or year is None or not title:
            return None

        listing_url = self._resolve_listing_url(attrs, payload, list_id, str(title), html)
        if not listing_url:
            return None

        location = self._format_location(
            pick_first(attrs.get("regionName"), attrs.get("stateName")),
            attrs.get("subareaName") or attrs.get("areaName"),
        )

        return {
            "source": self.source,
            "listing_url": listing_url,
            "variant": str(model_name).strip() if model_name else None,
            "year": year,
            "price_rm": price_rm,
            "mileage": parse_mileage_km(attrs.get("mileage")),
            "transmission": normalize_transmission(attrs.get("transmission")),
            "fuel_type": normalize_fuel_type(attrs.get("fueltype") or attrs.get("fuelType")),
            "location": location,
            "seller_type": seller_type_from_flags(company_ad=attrs.get("companyAd")),
            "posted_at": normalize_posted_at(
                pick_first(attrs.get("listTs"), attrs.get("adDate"), attrs.get("date"))
            ),
            "scraped_at": datetime.now(timezone.utc).replace(tzinfo=None),
            "_make": str(make or ""),
            "_title": str(title),
            "_model_group": str(model_group or ""),
        }

    def _resolve_listing_url(
    self,
    attrs: dict[str, Any],
    payload: dict[str, Any],
    list_id: str,
    title: str,
    html: str = "",
) -> str | None:
        if html and list_id:
            match = re.search(rf'href="([^"]*{re.escape(list_id)}\.htm[^"]*)"', html)
            if match:
                return absolutize_url(MUDAH_BASE, match.group(1)).split("?")[0]

        for candidate in (
            attrs.get("adviewUrl"),      # <-- was "adview_url"
            attrs.get("adview_url"),      # keep as a secondary check, harmless
            attrs.get("url"),
            attrs.get("adUrl"),
            payload.get("url"),
        ):
            url = absolutize_url(MUDAH_BASE, candidate if isinstance(candidate, str) else None)
            if url and ".htm" in url:
                return url.split("?")[0]

        links = payload.get("links") or attrs.get("links")
        if isinstance(links, dict):
            self_link = links.get("self")
            if isinstance(self_link, str):
                url = absolutize_url(MUDAH_BASE, self_link)
                if url:
                    return url.split("?")[0]
            elif isinstance(self_link, dict):
                url = absolutize_url(MUDAH_BASE, self_link.get("href"))
                if url:
                    return url.split("?")[0]

        if list_id and title:
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            if slug:
                return f"{MUDAH_BASE}/{slug}-{list_id}.htm"
        return None

    def _title_from_html(self, html: str, list_id: str) -> str | None:
        match = re.search(rf'href="([^"]*{re.escape(list_id)}\.htm)"', html)
        if not match:
            return None
        slug = match.group(1).rstrip("/").split("/")[-1].replace(".htm", "")
        return slug.replace("-", " ").title()

    def _format_location(self, region: Any, subarea: Any) -> str | None:
        parts = [str(p).strip() for p in (region, subarea) if p]
        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        return f"{parts[0]} - {parts[1]}"

    def _extract_detail_from_html(self, html: str) -> dict | None:
        """Fallback parser for listing detail fixture DOM."""
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("h1") or soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        if not title or not is_mercedes(title=title):
            return None

        canonical = normalize_scraped_class(title)
        if not canonical:
            return None

        icon_blocks = soup.select("#ad_view section img[alt]")
        year = None
        transmission = None
        mileage = None
        location = None
        for img in icon_blocks:
            alt = img.get("alt", "").strip()
            if re.fullmatch(r"\d{4}", alt):
                year = int(alt)
            elif alt.lower() in {"auto", "manual", "automatic"}:
                transmission = normalize_transmission(alt)
            elif re.search(r"\d+\s*k", alt, re.I):
                mileage = parse_mileage_km(alt)
            elif " - " in alt:
                location = alt

        canonical_link = soup.find("link", rel="canonical")
        listing_url = canonical_link["href"] if canonical_link and canonical_link.get("href") else None
        if not listing_url:
            return None

        price_match = re.search(r"RM\s*([\d,]+)", soup.get_text(" ", strip=True))
        price_rm = parse_price_rm(price_match.group(1)) if price_match else None
        if year is None or price_rm is None:
            return None

        variant_match = re.search(r"\b(C\d{3}|E\d{3}|A\d{3}|GL[ACSE]\d{0,3})\b", title, re.I)

        return {
            "source": self.source,
            "listing_url": listing_url.split("?")[0],
            "model": canonical,
            "variant": variant_match.group(1).upper() if variant_match else None,
            "year": year,
            "price_rm": price_rm,
            "mileage": mileage,
            "transmission": transmission,
            "fuel_type": None,
            "location": location,
            "seller_type": "unknown",
            "posted_at": None,
            "scraped_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }
