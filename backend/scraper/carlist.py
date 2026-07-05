"""Carlist.my Mercedes listing extractor.

Field map (verified against fixtures captured 2026-07):
- Search results: ``application/ld+json`` ItemList → itemListElement[*].item (Car/Product)
  - brand.name, model, vehicleModelDate, mileageFromOdometer.value
  - vehicleTransmission, fuelType, offers.price, mainEntityOfPage (canonical listing URL)
  - offers.seller.address.addressRegion, seller @type Organization → dealer
- Search HTML fallback: ``article.js--listing`` data-* attributes
- Listing detail: JSON-LD Car block + ``meta[name=WT.z_*]`` / ``ga:cad:details:*``
- Canonical search URL:
  https://www.carlist.my/cars-for-sale/mercedes-benz/c-class/c200/malaysia
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, TypedDict

from bs4 import BeautifulSoup

from ml.constants import is_mercedes, normalize_scraped_class
from scraper.common import (
    CARLIST_BASE,
    extract_json_ld_blocks,
    meta_content,
    normalize_fuel_type,
    normalize_posted_at,
    normalize_transmission,
    parse_mileage_km,
    parse_price_rm,
    pick_first,
    seller_type_from_flags,
)

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.carlist.my/cars-for-sale/mercedes-benz/c-class/c200/malaysia"


class ExtractSummary(TypedDict):
    fetched: int
    mercedes_kept: int
    skipped_non_mercedes: int
    skipped_unparseable: int


class CarlistExtractor:
    """Parse Carlist HTML (live or fixture) into normalised listing dicts."""

    source = "carlist"

    def extract_search_results(self, html: str) -> tuple[list[dict], ExtractSummary]:
        items = self._item_list_cars(html)
        if not items:
            items = self._article_cards(html)

        rows: list[dict] = []
        summary = ExtractSummary(
            fetched=len(items),
            mercedes_kept=0,
            skipped_non_mercedes=0,
            skipped_unparseable=0,
        )
        seen_urls: set[str] = set()

        for item in items:
            row = self._normalize_car_item(item)
            if row is None:
                summary["skipped_unparseable"] += 1
                continue
            if row["listing_url"] in seen_urls:
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
            seen_urls.add(row["listing_url"])
            rows.append(row)
            summary["mercedes_kept"] += 1

        return rows, summary

    def extract_listing_detail(self, html: str) -> dict | None:
        for block in extract_json_ld_blocks(html):
            if not isinstance(block, dict):
                continue
            types = block.get("@type")
            type_set = {types} if isinstance(types, str) else set(types or [])
            if "Car" in type_set or block.get("@type") == "Car":
                row = self._normalize_car_item(block)
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
                        return self._enrich_detail_from_meta(html, row)

        soup = BeautifulSoup(html, "html.parser")
        article = soup.find("article", class_=re.compile(r"js--listing"))
        if article:
            row = self._normalize_article(article)
            if row:
                return self._enrich_detail_from_meta(html, row)
        return None

    def _item_list_cars(self, html: str) -> list[dict[str, Any]]:
        cars: list[dict[str, Any]] = []
        for block in extract_json_ld_blocks(html):
            if not isinstance(block, dict):
                continue
            types = block.get("@type")
            if isinstance(types, list) and "ItemList" in types:
                for element in block.get("itemListElement", []):
                    item = element.get("item") if isinstance(element, dict) else None
                    if isinstance(item, dict):
                        cars.append(item)
        return cars

    def _article_cards(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        cards: list[dict[str, Any]] = []
        for article in soup.select("article.js--listing"):
            normalized = self._normalize_article(article)
            if normalized:
                cards.append(
                    {
                        "brand": {"name": normalized["_make"]},
                        "model": normalized.get("variant"),
                        "name": normalized["_title"],
                        "vehicleModelDate": normalized["year"],
                        "mileageFromOdometer": {"value": normalized.get("mileage")},
                        "vehicleTransmission": normalized.get("transmission"),
                        "fuelType": normalized.get("fuel_type"),
                        "mainEntityOfPage": normalized["listing_url"],
                        "offers": {"price": normalized["price_rm"]},
                        "_model_group": normalized.get("_model_group", ""),
                    }
                )
        return cards

    def _normalize_article(self, article) -> dict | None:
        title = article.get("data-title") or article.get("data-display-title")
        listing_url = article.get("data-url")
        year_raw = article.get("data-year")
        if not title or not listing_url or not year_raw:
            return None
        try:
            year = int(year_raw)
        except (TypeError, ValueError):
            return None

        make = article.get("data-make") or "Mercedes-Benz"
        return {
            "source": self.source,
            "listing_url": str(listing_url).split("?")[0],
            "variant": article.get("data-model"),
            "year": year,
            "price_rm": None,
            "mileage": None,
            "transmission": normalize_transmission(article.get("data-transmission")),
            "fuel_type": None,
            "location": None,
            "seller_type": "unknown",
            "posted_at": None,
            "scraped_at": datetime.now(timezone.utc).replace(tzinfo=None),
            "_make": make,
            "_title": title,
            "_model_group": article.get("data-model-group") or "",
        }

    def _normalize_car_item(self, item: dict[str, Any]) -> dict | None:
        brand = item.get("brand") or {}
        make = brand.get("name") if isinstance(brand, dict) else str(brand)
        title = pick_first(item.get("name"), item.get("title"))
        year_raw = pick_first(item.get("vehicleModelDate"), item.get("year"))
        try:
            year = int(str(year_raw)[:4]) if year_raw is not None else None
        except (TypeError, ValueError):
            year = None

        offers = item.get("offers") or {}
        price_rm = parse_price_rm(offers.get("price") if isinstance(offers, dict) else None)
        listing_url = pick_first(item.get("mainEntityOfPage"), item.get("url"))
        if isinstance(listing_url, dict):
            listing_url = listing_url.get("@id")
        if not title or not listing_url or year is None or price_rm is None:
            return None

        mileage_block = item.get("mileageFromOdometer") or {}
        mileage = parse_mileage_km(
            mileage_block.get("value") if isinstance(mileage_block, dict) else mileage_block
        )

        seller = offers.get("seller") if isinstance(offers, dict) else {}
        profile_type = ""
        location = None
        if isinstance(seller, dict):
            if seller.get("@type") == "Organization":
                profile_type = "Dealer"
            address = seller.get("address") or {}
            if isinstance(address, dict):
                location = pick_first(address.get("addressRegion"), address.get("addressLocality"))

        engine = item.get("vehicleEngine") or {}
        variant = pick_first(item.get("model"), engine.get("engineType") if isinstance(engine, dict) else None)

        return {
            "source": self.source,
            "listing_url": str(listing_url).split("#")[0].split("?")[0],
            "variant": str(variant).strip() if variant else None,
            "year": year,
            "price_rm": price_rm,
            "mileage": mileage,
            "transmission": normalize_transmission(item.get("vehicleTransmission")),
            "fuel_type": normalize_fuel_type(item.get("fuelType")),
            "location": location,
            "seller_type": seller_type_from_flags(profile_type=profile_type),
            "posted_at": normalize_posted_at(item.get("datePublished")),
            "scraped_at": datetime.now(timezone.utc).replace(tzinfo=None),
            "_make": str(make or ""),
            "_title": str(title),
            "_model_group": "",
        }

    def _enrich_detail_from_meta(self, html: str, row: dict) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        row["price_rm"] = row.get("price_rm") or parse_price_rm(meta_content(soup, "WT.z_price"))
        row["transmission"] = row.get("transmission") or normalize_transmission(
            meta_content(soup, "WT.z_transmission")
        )
        row["fuel_type"] = row.get("fuel_type") or normalize_fuel_type(
            meta_content(soup, "WT.z_Fueltype")
        )
        row["location"] = row.get("location") or meta_content(soup, "WT.z_location")
        row["variant"] = row.get("variant") or meta_content(soup, "WT.z_model")
        if row.get("year") is None:
            year_meta = meta_content(soup, "WT.z_year")
            if year_meta:
                try:
                    row["year"] = int(year_meta)
                except ValueError:
                    pass
        row["seller_type"] = seller_type_from_flags(
            profile_type=meta_content(soup, "ga:cad:details:profile_type") or ""
        )
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            row["listing_url"] = str(canonical["href"]).split("?")[0]
        return row
