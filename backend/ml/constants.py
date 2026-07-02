"""Canonical Mercedes model class labels and scraper configuration.

This module is the single source of truth for model normalization across
ingest (ml/ingest.py) and scrapers (scraper/mudah.py, scraper/carlist.py).
Any raw CSV or scraped model value must map to exactly one of these labels.

The vehicle_profiles.model constraint (Phase 00) enforces this set.
"""

# Canonical Mercedes-Benz model class labels.
# Keys: normalized input (upper-case, leading/trailing stripped).
# Values: canonical label used in training_data and market_listings.
#
# Rationale: merc.csv raw `model` values have inconsistent casing and spacing
# (e.g. "SL CLASS", "SL Class", "sl class" all appear).
# We strip, uppercase, and map to one canonical label per class.
# Scraped listings also map to these labels for consistency.

CANONICAL_MODELS = {
    # A-Class
    "A CLASS": "A_CLASS",
    "A-CLASS": "A_CLASS",
    "A": "A_CLASS",
    # B-Class
    "B CLASS": "B_CLASS",
    "B-CLASS": "B_CLASS",
    "B": "B_CLASS",
    # C-Class (most common; multiple variants)
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
    # SL-Class (roadster/convertible)
    "SL CLASS": "SL_CLASS",
    "SL-CLASS": "SL_CLASS",
    "SL": "SL_CLASS",
    # SLK-Class (compact roadster)
    "SLK CLASS": "SLK_CLASS",
    "SLK-CLASS": "SLK_CLASS",
    "SLK": "SLK_CLASS",
    # CLA-Class (compact sports sedan)
    "CLA CLASS": "CLA_CLASS",
    "CLA-CLASS": "CLA_CLASS",
    "CLA": "CLA_CLASS",
    # GLC-Class (compact SUV)
    "GLC CLASS": "GLC_CLASS",
    "GLC-CLASS": "GLC_CLASS",
    "GLC": "GLC_CLASS",
    # GLE-Class (mid-size SUV)
    "GLE CLASS": "GLE_CLASS",
    "GLE-CLASS": "GLE_CLASS",
    "GLE": "GLE_CLASS",
    # GLA-Class (subcompact SUV)
    "GLA CLASS": "GLA_CLASS",
    "GLA-CLASS": "GLA_CLASS",
    "GLA": "GLA_CLASS",
    # AMG models (high-performance variants)
    # Note: scraped data may list "AMG" as a separate class; we treat it as a variant
    # and map the base model (e.g. "C 63 AMG" -> "C_CLASS").
    # This is decided post-analysis of merc.csv; if AMG is its own row type, 
    # it should get "AMG" as a standalone label. For now, assume base-model+variant.
    # G-Class (SUV/off-road)
    "G CLASS": "G_CLASS",
    "G-CLASS": "G_CLASS",
    "G": "G_CLASS",
}

# Numeric-only model values that appear in merc.csv but lack a class designation.
# These are dropped during ingest with a logged count.
NUMERIC_ONLY_MODELS = {"230", "220", "200", "180"}


# Scraper configuration defaults.
# These must align with robots.txt Crawl-delay at Gate 1.

SCRAPER_DEFAULTS = {
    "max_pages_per_site": 10,  # Conservative: ~50-100 listings per site per run.
    "max_listings_per_run": 100,  # Hard cap: polite collection for sample evaluation.
    # SCRAPER_RATE_LIMIT_SECONDS is in .env (default 4 seconds between requests).
    # At Gate 1, reconcile with each site's robots.txt Crawl-delay.
}


def normalize_model(raw_model: str) -> str | None:
    """Normalize a raw model string to a canonical label.

    Args:
        raw_model: The raw model value from merc.csv or a scraper.

    Returns:
        The canonical model label (e.g., "C_CLASS") if recognized.
        None if the model is unrecognized or numeric-only.
    """
    if not raw_model:
        return None

    cleaned = raw_model.strip().upper()

    # Check numeric-only list first.
    if cleaned in NUMERIC_ONLY_MODELS:
        return None

    # Look up in canonical map.
    return CANONICAL_MODELS.get(cleaned)


def get_canonical_model_set() -> set[str]:
    """Return the set of all valid canonical model labels.

    Used by:
    - vehicle_profiles.model constraint validation (Phase 03).
    - Scraper normalization checks.
    """
    return set(CANONICAL_MODELS.values())
