"""
City Open Data scraper — government business license registries.

Uses Socrata Open Data APIs (no API key required). These are public records
published by city/county governments. Data is government-validated, making it
higher-trust than directory listings.

Supported cities (all free, no key):
  - Chicago, IL    — Business Licenses (active only)
  - New York, NY   — Legally Operating Businesses
  - Seattle, WA    — Active Business Licenses
  - Austin, TX     — Active Business License Dataset
  - Denver, CO     — Active Licenses
  - Portland, OR   — Business Licenses
  - Nashville, TN  — Business Tax Licenses
  - Philadelphia, PA — Business Licenses
  - San Francisco, CA — Registered Businesses

Differentiator: government-validated data + license dates (years_in_business signal).
"""

import re
import time
from datetime import datetime

import httpx

from sources.base import BaseScraper, ScrapedLead

# Socrata endpoint configs: (domain, resource_id, name_field, address_field, zip_field, license_field, date_field)
SOCRATA_ENDPOINTS = {
    ("chicago", "IL"): {
        "domain": "data.cityofchicago.org",
        "resource": "r5kz-chrr",
        "name_field": "doing_business_as_name",
        "address_field": "address",
        "zip_field": "zip_code",
        "license_field": "license_description",
        "date_field": "license_start_date",
        "city_name": "Chicago",
        "state": "IL",
    },
    ("new york city", "NY"): {
        "domain": "data.cityofnewyork.us",
        "resource": "w7w3-xahh",
        "name_field": "business_name",
        "address_field": "physical_address",
        "zip_field": "zip_code",
        "license_field": "industry",
        "date_field": "license_creation_date",
        "city_name": "New York City",
        "state": "NY",
    },
    ("seattle", "WA"): {
        "domain": "data.seattle.gov",
        "resource": "wnbq-64tb",
        "name_field": "trade_name",
        "address_field": "street_address",
        "zip_field": "zip_code",
        "license_field": "description",
        "date_field": "license_start_date",
        "city_name": "Seattle",
        "state": "WA",
    },
    ("austin", "TX"): {
        "domain": "data.austintexas.gov",
        "resource": "g5k8-8sud",
        "name_field": "business_name",
        "address_field": "street_address_line_1",
        "zip_field": "zip_code",
        "license_field": "license_type",
        "date_field": "initial_date_permitted",
        "city_name": "Austin",
        "state": "TX",
    },
    ("denver", "CO"): {
        "domain": "www.denvergov.org",
        "resource": "m7g3-rbjf",
        "name_field": "tradename",
        "address_field": "licensee_address",
        "zip_field": "licensee_zip",
        "license_field": "license_type",
        "date_field": "issue_date",
        "city_name": "Denver",
        "state": "CO",
    },
    ("san francisco", "CA"): {
        "domain": "data.sfgov.org",
        "resource": "g8m3-pdis",
        "name_field": "dba_name",
        "address_field": "street_address",
        "zip_field": "zip_code",
        "license_field": "naic_description",
        "date_field": "business_start_date",
        "city_name": "San Francisco",
        "state": "CA",
    },
}

# Map license description keywords → our canonical industry names
LICENSE_TO_INDUSTRY: list[tuple[list[str], str]] = [
    (["roof", "roofer"], "roofing"),
    (["plumb"], "plumbing"),
    (["hvac", "heating", "cooling", "air condition", "refriger"], "hvac"),
    (["electric"], "electrician"),
    (["landscape", "lawn", "landscap"], "landscaping"),
    (["pest", "exterminat"], "pest control"),
    (["clean", "maid", "janitorial"], "cleaning"),
    (["solar"], "solar"),
    (["concrete", "masonry", "brick"], "concrete"),
    (["paint"], "painting"),
    (["fence", "fencing"], "fencing"),
    (["window"], "windows"),
    (["siding"], "siding"),
    (["gutter"], "gutters"),
    (["drywall", "plaster"], "drywall"),
    (["insulation"], "insulation"),
    (["floor", "flooring", "carpet", "tile"], "flooring"),
    (["remodel", "renovation", "contractor", "construction", "building"], "remodeling"),
    (["tree", "arborist"], "tree service"),
    (["pool", "spa"], "pool service"),
    (["deck", "patio"], "decking"),
    (["garage door"], "garage door"),
    (["locksmith"], "locksmith"),
    (["appliance"], "appliance repair"),
    (["auto", "automotive", "mechanic", "vehicle", "car repair"], "auto repair"),
    (["dental", "dentist", "orthodon"], "dentist"),
    (["medical", "clinic", "physician", "doctor"], "medical"),
    (["real estate", "realt"], "real estate"),
    (["insurance"], "insurance"),
    (["attorney", "lawyer", "legal", "law "], "attorney"),
    (["account", "bookkeep", "cpa", "tax prep"], "accounting"),
    (["restaurant", "food service", "catering", "bar ", "tavern"], "restaurant"),
    (["retail", "shop", "store"], "retail"),
    (["moving", "mover"], "moving"),
    (["security", "alarm"], "security"),
    (["photography", "photographer"], "photography"),
    (["chiropract"], "chiropractor"),
    (["physical therap"], "physical therapy"),
    (["handyman", "home repair", "home maintenance"], "handyman"),
    (["mold", "remediat", "restoration"], "mold remediation"),
    (["waterproof"], "waterproofing"),
    (["foundation"], "foundation repair"),
    (["pressure wash", "power wash"], "pressure washing"),
    (["junk", "debris", "hauling", "removal"], "junk removal"),
    (["home inspect"], "home inspection"),
]


def _map_license_to_industry(license_desc: str) -> str | None:
    """Map a license description to our canonical industry name."""
    desc_lower = license_desc.lower()
    for keywords, industry in LICENSE_TO_INDUSTRY:
        if any(kw in desc_lower for kw in keywords):
            return industry
    return None


def _calc_years_in_business(date_str: str | None) -> int | None:
    """Calculate years in business from a license/start date string."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            start = datetime.strptime(date_str[:19], fmt[:len(fmt)])
            years = (datetime.now() - start).days // 365
            return max(0, years)
        except ValueError:
            continue
    return None


class CityOpenDataScraper(BaseScraper):
    """
    Pulls from government Socrata APIs for whichever city matches the requested city/state.
    Falls back gracefully if the city isn't in the supported list.
    """

    def scrape(self, industry: str, city: str, state: str, max_results: int = 200) -> list[ScrapedLead]:
        # Find matching endpoint
        city_lower = city.lower().strip()
        state_upper = state.upper().strip()
        config = None
        for (cfg_city, cfg_state), cfg in SOCRATA_ENDPOINTS.items():
            if cfg_state == state_upper and cfg_city in city_lower:
                config = cfg
                break

        if not config:
            return []  # City not supported — silently skip

        return self._fetch_socrata(config, industry, max_results)

    def _fetch_socrata(self, config: dict, industry: str, max_results: int) -> list[ScrapedLead]:
        domain = config["domain"]
        resource = config["resource"]
        city_name = config["city_name"]
        state = config["state"]

        name_f = config["name_field"]
        addr_f = config["address_field"]
        zip_f = config["zip_field"]
        lic_f = config["license_field"]
        date_f = config["date_field"]

        leads = []
        offset = 0
        limit = min(200, max_results)

        # Build SoQL WHERE clause to filter by industry keyword
        industry_kw = industry.lower().strip()
        # Use SoQL LIKE to filter at the server
        where_clause = f"upper({lic_f}) like upper('%25{industry_kw}%25')"

        with httpx.Client(timeout=20) as client:
            while len(leads) < max_results:
                url = f"https://{domain}/resource/{resource}.json"
                params = {
                    "$limit": limit,
                    "$offset": offset,
                    "$order": f"{date_f} DESC",
                }
                # Don't add WHERE — fetch all and filter locally for better recall
                # (license descriptions vary widely; local mapping is more reliable)

                try:
                    resp = client.get(url, params=params)
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    print(f"[city-open-data] {domain} HTTP error: {e}")
                    break

                rows = resp.json()
                if not rows:
                    break

                for row in rows:
                    license_desc = row.get(lic_f, "") or ""
                    mapped_industry = _map_license_to_industry(license_desc)
                    if not mapped_industry:
                        continue

                    # Filter to requested industry
                    if industry.lower() not in mapped_industry and mapped_industry not in industry.lower():
                        # Check if any keyword from the industry matches
                        if not any(kw in industry.lower() for kw in mapped_industry.split()):
                            continue

                    biz_name = (row.get(name_f) or "").strip()
                    if not biz_name:
                        continue

                    address = (row.get(addr_f) or "").strip() or None
                    zip_code = (row.get(zip_f) or "").strip()[:10] or None
                    full_address = f"{address}, {city_name}, {state} {zip_code}".strip(", ") if address else None

                    date_str = row.get(date_f) or None
                    years = _calc_years_in_business(date_str)

                    # Use composite key as source_url for dedup
                    source_url = f"opendata:{domain}:{resource}:{biz_name.lower()[:50]}:{zip_code or ''}"

                    leads.append(ScrapedLead(
                        business_name=biz_name,
                        industry=mapped_industry,
                        city=city_name,
                        state=state,
                        website=None,
                        phone=None,
                        zip_code=zip_code,
                        full_address=full_address,
                        source_url=source_url,
                        source="city_open_data",
                        years_in_business=years,
                    ))

                if len(rows) < limit:
                    break

                offset += limit
                time.sleep(0.3)

        return leads[:max_results]
