"""Canonical Mercedes model class labels and scraper configuration.

Single source of truth for model normalization across ingest (ml/ingest.py)
and scrapers (scraper/mudah.py, scraper/carlist.py).
"""

from __future__ import annotations

import re

# Every raw merc.csv `model` spelling maps to exactly one canonical label.
CANONICAL_MODELS = {
    # A-Class
    "A CLASS": "A_CLASS",
    "A-CLASS": "A_CLASS",
    "A": "A_CLASS",
    # B-Class
    "B CLASS": "B_CLASS",
    "B-CLASS": "B_CLASS",
    "B": "B_CLASS",
    # C-Class
    "C CLASS": "C_CLASS",
    "C-CLASS": "C_CLASS",
    "C": "C_CLASS",
    "C COUPE": "C_CLASS",
    "C-COUPE": "C_CLASS",
    # E-Class
    "E CLASS": "E_CLASS",
    "E-CLASS": "E_CLASS",
    "E": "E_CLASS",
    "E COUPE": "E_CLASS",
    "E-COUPE": "E_CLASS",
    # S-Class
    "S CLASS": "S_CLASS",
    "S-CLASS": "S_CLASS",
    "S": "S_CLASS",
    "S COUPE": "S_CLASS",
    "S-COUPE": "S_CLASS",
    # SL-Class
    "SL CLASS": "SL_CLASS",
    "SL-CLASS": "SL_CLASS",
    "SL": "SL_CLASS",
    # SLK-Class
    "SLK CLASS": "SLK_CLASS",
    "SLK-CLASS": "SLK_CLASS",
    "SLK": "SLK_CLASS",
    # CLA-Class
    "CLA CLASS": "CLA_CLASS",
    "CLA-CLASS": "CLA_CLASS",
    "CLA": "CLA_CLASS",
    # GLC-Class
    "GLC CLASS": "GLC_CLASS",
    "GLC-CLASS": "GLC_CLASS",
    "GLC": "GLC_CLASS",
    # GLE-Class
    "GLE CLASS": "GLE_CLASS",
    "GLE-CLASS": "GLE_CLASS",
    "GLE": "GLE_CLASS",
    # GLA-Class
    "GLA CLASS": "GLA_CLASS",
    "GLA-CLASS": "GLA_CLASS",
    "GLA": "GLA_CLASS",
    # G-Class
    "G CLASS": "G_CLASS",
    "G-CLASS": "G_CLASS",
    "G": "G_CLASS",
    # GL-Class (full-size SUV; predecessor naming in merc.csv)
    "GL CLASS": "GL_CLASS",
    "GL-CLASS": "GL_CLASS",
    "GL": "GL_CLASS",
    # CLS-Class
    "CLS CLASS": "CLS_CLASS",
    "CLS-CLASS": "CLS_CLASS",
    "CLS": "CLS_CLASS",
    # CL-Class
    "CL CLASS": "CL_CLASS",
    "CL-CLASS": "CL_CLASS",
    "CL": "CL_CLASS",
    # V-Class
    "V CLASS": "V_CLASS",
    "V-CLASS": "V_CLASS",
    "V": "V_CLASS",
    # M-Class (legacy SUV label in merc.csv)
    "M CLASS": "M_CLASS",
    "M-CLASS": "M_CLASS",
    "M": "M_CLASS",
    # GLS-Class
    "GLS CLASS": "GLS_CLASS",
    "GLS-CLASS": "GLS_CLASS",
    "GLS": "GLS_CLASS",
    # CLC-Class
    "CLC CLASS": "CLC_CLASS",
    "CLC-CLASS": "CLC_CLASS",
    "CLC": "CLC_CLASS",
    # R-Class
    "R CLASS": "R_CLASS",
    "R-CLASS": "R_CLASS",
    "R": "R_CLASS",
}

# Numeric-only rows lack a class designation — dropped during ingest with logged count.
NUMERIC_ONLY_MODELS = {"230", "220", "200", "180"}

SCRAPER_DEFAULTS = {
    "max_pages_per_site": 10,
    "max_listings_per_run": 100,
}

# Longest token first so GLC matches before GL, etc.
_SCRAPED_CLASS_TOKENS: tuple[tuple[str, str], ...] = (
    ("MERCEDES-AMG GT", "AMG_GT_CLASS"),
    ("GLS-CLASS", "GLS_CLASS"),
    ("GLS CLASS", "GLS_CLASS"),
    ("GLS", "GLS_CLASS"),
    ("GLE-CLASS", "GLE_CLASS"),
    ("GLE CLASS", "GLE_CLASS"),
    ("GLE", "GLE_CLASS"),
    ("GLC-CLASS", "GLC_CLASS"),
    ("GLC CLASS", "GLC_CLASS"),
    ("GLC", "GLC_CLASS"),
    ("GLA-CLASS", "GLA_CLASS"),
    ("GLA CLASS", "GLA_CLASS"),
    ("GLA", "GLA_CLASS"),
    ("CLA-CLASS", "CLA_CLASS"),
    ("CLA CLASS", "CLA_CLASS"),
    ("CLA", "CLA_CLASS"),
    ("CLS-CLASS", "CLS_CLASS"),
    ("CLS CLASS", "CLS_CLASS"),
    ("CLS", "CLS_CLASS"),
    ("CLC-CLASS", "CLC_CLASS"),
    ("CLC CLASS", "CLC_CLASS"),
    ("CLC", "CLC_CLASS"),
    ("CLK-CLASS", "CLK_CLASS"),
    ("CLK CLASS", "CLK_CLASS"),
    ("CLK", "CLK_CLASS"),
    ("SLK-CLASS", "SLK_CLASS"),
    ("SLK CLASS", "SLK_CLASS"),
    ("SLK", "SLK_CLASS"),
    ("SL-CLASS", "SL_CLASS"),
    ("SL CLASS", "SL_CLASS"),
    ("GL-CLASS", "GL_CLASS"),
    ("GL CLASS", "GL_CLASS"),
    ("V-CLASS", "V_CLASS"),
    ("V CLASS", "V_CLASS"),
    ("M-CLASS", "M_CLASS"),
    ("M CLASS", "M_CLASS"),
    ("R-CLASS", "R_CLASS"),
    ("R CLASS", "R_CLASS"),
    ("CL-CLASS", "CL_CLASS"),
    ("CL CLASS", "CL_CLASS"),
    ("G-CLASS", "G_CLASS"),
    ("G CLASS", "G_CLASS"),
    ("A-CLASS", "A_CLASS"),
    ("A CLASS", "A_CLASS"),
    ("B-CLASS", "B_CLASS"),
    ("B CLASS", "B_CLASS"),
    ("C-CLASS", "C_CLASS"),
    ("C CLASS", "C_CLASS"),
    ("E-CLASS", "E_CLASS"),
    ("E CLASS", "E_CLASS"),
    ("S-CLASS", "S_CLASS"),
    ("S CLASS", "S_CLASS"),
)

MERCEDES_MARKERS = ("mercedes-benz", "mercedes benz", "mercedes")
MERCEDES_BRANDS = {"mercedes-benz", "mercedes benz", "mercedes"}

def normalize_model(raw_model: str) -> str | None:
    """Normalize a raw merc.csv model string to a canonical label."""
    if not raw_model:
        return None

    cleaned = raw_model.strip().upper()
    if cleaned in NUMERIC_ONLY_MODELS:
        return None
    return CANONICAL_MODELS.get(cleaned)


def normalize_scraped_class(
    title: str,
    *,
    model_group: str = "",
    make: str = "",
) -> str | None:
    """Map a scraped listing title/make/model-group to a canonical class label."""
    if model_group:
        mapped = normalize_model(model_group.replace("-", " "))
        if mapped:
            return mapped

    haystack = f"{make} {title}".upper()
    if not is_mercedes(make=make, title=title):
        return None

    for token, label in _SCRAPED_CLASS_TOKENS:
        if token in haystack:
            return label

    # Variant codes like C200, E300, GLA200
    variant_match = re.search(
        r"\b(GLA|GLB|GLC|GLE|GLS|CLA|CLS|CLK|SLK|SL|GL|CL|[ABCESGV])\s*-?\s*(\d{2,3})\b",
        haystack,
    )
    if variant_match:
        prefix = variant_match.group(1)
        if prefix == "GL":
            return "GL_CLASS"
        return normalize_model(f"{prefix} CLASS")

    return None


def is_mercedes(*, make: str = "", title: str = "") -> bool:
    """Return True when make/title indicates a Mercedes-Benz vehicle."""
    text = f"{make} {title}".lower()
    return any(marker in text for marker in MERCEDES_MARKERS)


def get_canonical_model_set() -> set[str]:
    """Return the set of all valid canonical model labels."""
    labels = set(CANONICAL_MODELS.values())
    labels.add("CLK_CLASS")
    labels.add("AMG_GT_CLASS")
    return labels
