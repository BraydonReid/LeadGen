"""
Yelp API monthly budget manager.

5,000 calls/month = ~166/day. Strategy:
  - Spend calls on highest-value industry × city combos first
  - Each Yelp call returns up to 50 leads → 5,000 calls = 250,000 potential leads
  - Track usage in a JSON file with monthly reset
  - Enforce daily cap so budget isn't burned in the first week
  - Skip cities/industries with low lead value (use free scrapers for those)
"""

import json
from datetime import datetime, date
from pathlib import Path

BUDGET_FILE = Path("/app/history/yelp_budget.json")
MONTHLY_LIMIT = 5000
DAILY_LIMIT = 450   # ~500/day free tier, with small buffer


def _load() -> dict:
    BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    if BUDGET_FILE.exists():
        try:
            return json.loads(BUDGET_FILE.read_text())
        except Exception:
            pass
    return {"month": date.today().strftime("%Y-%m"), "monthly_used": 0, "daily_used": 0, "today": str(date.today())}


def _save(data: dict):
    BUDGET_FILE.write_text(json.dumps(data, indent=2))


def _refresh(data: dict) -> dict:
    today = str(date.today())
    current_month = date.today().strftime("%Y-%m")

    if data.get("month") != current_month:
        # New month — reset everything
        data["month"] = current_month
        data["monthly_used"] = 0
        data["daily_used"] = 0
        data["today"] = today

    if data.get("today") != today:
        # New day — reset daily count
        data["daily_used"] = 0
        data["today"] = today

    return data


def can_call(calls: int = 1) -> bool:
    """Check if we have budget remaining for `calls` API calls."""
    data = _refresh(_load())
    monthly_remaining = MONTHLY_LIMIT - data["monthly_used"]
    daily_remaining = DAILY_LIMIT - data["daily_used"]
    return monthly_remaining >= calls and daily_remaining >= calls


def record_calls(calls: int):
    """Record that `calls` API calls were made."""
    data = _refresh(_load())
    data["monthly_used"] += calls
    data["daily_used"] += calls
    _save(data)


def get_status() -> dict:
    data = _refresh(_load())
    return {
        "month": data["month"],
        "monthly_used": data["monthly_used"],
        "monthly_remaining": MONTHLY_LIMIT - data["monthly_used"],
        "daily_used": data["daily_used"],
        "daily_remaining": DAILY_LIMIT - data["daily_used"],
    }


# ── Priority scoring — decide which combos deserve a Yelp call ───────────────
# Yelp is best used on high-value industries in large cities.
# Free scrapers handle low-value combos just fine.

# Industry value tiers — base price from pricing.py
HIGH_VALUE_INDUSTRIES = {
    "attorney", "medical", "insurance", "dentist", "solar",
    "roofing", "hvac", "plumbing", "electrician", "real estate",
    "chiropractor", "financial advisor", "mortgage", "pest control",
    "remodeling", "windows", "siding",
}

MEDIUM_VALUE_INDUSTRIES = {
    "landscaping", "tree service", "painting", "flooring", "concrete",
    "fencing", "gutters", "insulation", "waterproofing", "foundation repair",
    "auto repair", "cleaning", "pool installation", "pool service",
    "security", "garage door", "generator", "carpet cleaning",
}

# City tiers — larger cities = more leads per call = better ROI
TIER1_CITIES = {
    "new york city", "los angeles", "chicago", "houston", "phoenix",
    "philadelphia", "san antonio", "san diego", "dallas", "san jose",
    "austin", "jacksonville", "fort worth", "columbus", "charlotte",
    "san francisco", "indianapolis", "seattle", "denver", "nashville",
    "oklahoma city", "el paso", "washington", "boston", "las vegas",
    "portland", "memphis", "louisville", "baltimore", "milwaukee",
    "albuquerque", "tucson", "fresno", "sacramento", "mesa",
    "kansas city", "atlanta", "omaha", "colorado springs", "raleigh",
    "long beach", "virginia beach", "miami", "oakland", "minneapolis",
    "tampa", "tulsa", "arlington", "new orleans",
}

TIER2_CITIES = {
    "aurora", "wichita", "bakersfield", "anaheim", "santa ana",
    "corpus christi", "riverside", "st. louis", "lexington", "stockton",
    "pittsburgh", "anchorage", "greensboro", "plano", "henderson",
    "newark", "lincoln", "orlando", "st. paul", "jersey city",
    "chandler", "laredo", "norfolk", "madison", "durham", "lubbock",
    "winston-salem", "garland", "glendale", "hialeah", "reno",
    "baton rouge", "irvine", "chesapeake", "scottsdale", "north las vegas",
    "fremont", "gilbert", "madison", "shreveport", "boise",
}


def should_use_yelp(industry: str, city: str) -> bool:
    """
    Return True if this industry × city combo is worth a Yelp API call.
    Preserves budget for the highest-ROI combinations.
    """
    if not can_call():
        return False

    industry_lower = industry.lower()
    city_lower = city.lower()

    # Always use Yelp for high-value industry in tier1 city
    if industry_lower in HIGH_VALUE_INDUSTRIES and city_lower in TIER1_CITIES:
        return True

    # Use Yelp for high-value industry in tier2 city
    if industry_lower in HIGH_VALUE_INDUSTRIES and city_lower in TIER2_CITIES:
        return True

    # Use Yelp for medium-value industry in tier1 city
    if industry_lower in MEDIUM_VALUE_INDUSTRIES and city_lower in TIER1_CITIES:
        return True

    # For everything else, free scrapers are sufficient
    return False
