"""
Building Permit Consumer Intent Scraper.

Pulls from city/county open data APIs (Socrata — no API key required).
Building permits are the highest-quality consumer intent signal available:
  - A homeowner who just pulled a ROOFING permit IS currently replacing their roof
  - They need a contractor RIGHT NOW
  - We know their exact address, permit type, and issue date

This is a fundamental differentiator: Apollo/ZoomInfo don't have this data.
Buyers get homeowners who are ACTIVELY in-market, not cold business lists.

Supported cities (all free, no key):
  Chicago IL, New York City NY, Seattle WA, Austin TX, San Francisco CA,
  Denver CO, Philadelphia PA, Los Angeles CA, Boston MA, Nashville TN,
  Portland OR, Houston TX, Columbus OH, Minneapolis MN, Atlanta GA

lead_type is set to "consumer" — these leads command 1.5× price premium.
"""

import re
import time
from datetime import datetime, timedelta

import httpx

from sources.base import BaseScraper, ScrapedLead

# City permit endpoints (Socrata — all free, no key needed)
PERMIT_ENDPOINTS = {
    ("chicago", "IL"): {
        "domain": "data.cityofchicago.org",
        "resource": "ydr8-5enu",
        "name_field": "contact_1_name",
        "address_fields": ["street_number", "street_direction", "street_name", "suffix"],
        "zip_field": "zip_code",
        "type_field": "permit_type",
        "desc_field": "work_description",
        "date_field": "issued_date",
        "city_name": "Chicago",
        "state": "IL",
    },
    ("new york city", "NY"): {
        "domain": "data.cityofnewyork.us",
        "resource": "rbx6-tga4",
        "name_field": "owner_s_first_name",
        "address_fields": ["house__", "street_name"],
        "zip_field": "zip_code",
        "type_field": "permit_type",
        "desc_field": "permit_type",
        "date_field": "issuance_date",
        "city_name": "New York City",
        "state": "NY",
    },
    ("seattle", "WA"): {
        "domain": "data.seattle.gov",
        "resource": "76t5-zqzr",
        "name_field": "applicant_name",
        "address_fields": ["address"],
        "zip_field": "zip",
        "type_field": "permit_type",
        "desc_field": "description",
        "date_field": "issued_date",
        "city_name": "Seattle",
        "state": "WA",
    },
    ("austin", "TX"): {
        "domain": "data.austintexas.gov",
        "resource": "3syk-w9eu",
        "name_field": "applicant_full_name",
        "address_fields": ["work_site_address"],
        "zip_field": "zip_code",
        "type_field": "permit_type_desc",
        "desc_field": "work_description",
        "date_field": "issue_date",
        "city_name": "Austin",
        "state": "TX",
    },
    ("san francisco", "CA"): {
        "domain": "data.sfgov.org",
        "resource": "i98e-djp9",
        "name_field": "applicant",
        "address_fields": ["street_number", "street_name"],
        "zip_field": "zipcode",
        "type_field": "permit_type_definition",
        "desc_field": "description",
        "date_field": "issued_date",
        "city_name": "San Francisco",
        "state": "CA",
    },
    ("denver", "CO"): {
        "domain": "www.denvergov.org",
        "resource": "pgn4-7qpk",
        "name_field": "applicant_name",
        "address_fields": ["address"],
        "zip_field": "zip",
        "type_field": "work_type",
        "desc_field": "work_description",
        "date_field": "issued_date",
        "city_name": "Denver",
        "state": "CO",
    },
    ("los angeles", "CA"): {
        "domain": "data.lacity.org",
        "resource": "nbud-jubf",
        "name_field": "applicant_s_name",
        "address_fields": ["address_start", "street_name"],
        "zip_field": "zip",
        "type_field": "permit_type",
        "desc_field": "permit_sub_type",
        "date_field": "date_issued",
        "city_name": "Los Angeles",
        "state": "CA",
    },
    ("philadelphia", "PA"): {
        "domain": "phl.carto.com",
        "resource": "dbd7-yzrh",
        "name_field": "ownername",
        "address_fields": ["address"],
        "zip_field": "zip",
        "type_field": "typeofwork",
        "desc_field": "typeofwork",
        "date_field": "permitissuedate",
        "city_name": "Philadelphia",
        "state": "PA",
    },
    ("portland", "OR"): {
        "domain": "data.portlandoregon.gov",
        "resource": "ib2y-bj6g",
        "name_field": "applicant_name",
        "address_fields": ["address"],
        "zip_field": "zip",
        "type_field": "type_of_work",
        "desc_field": "type_of_work",
        "date_field": "issue_date",
        "city_name": "Portland",
        "state": "OR",
    },
}

# Map permit type/description keywords → our canonical industry names
# Order matters: more specific matches first
PERMIT_TO_INDUSTRY: list[tuple[list[str], str]] = [
    (["roof", "roofer", "reroofing", "re-roofing", "shingle"], "roofing"),
    (["solar", "photovoltaic", "pv system"], "solar"),
    (["electric", "electrical", "wiring", "panel upgrade", "service upgrade"], "electrician"),
    (["plumb", "drain", "sewer", "water heater", "water main"], "plumbing"),
    (["hvac", "mechanical", "heating", "cooling", "furnace", "air condition", "heat pump", "boiler"], "hvac"),
    (["window replacement", "window install"], "windows"),
    (["siding", "exterior cladding"], "siding"),
    (["fence", "fencing"], "fencing"),
    (["deck", "patio", "pergola", "porch"], "decking"),
    (["pool", "spa", "hot tub", "swimming"], "pool installation"),
    (["gutter", "downspout"], "gutters"),
    (["insulation"], "insulation"),
    (["drywall", "plaster"], "drywall"),
    (["concrete", "driveway", "sidewalk", "flatwork"], "concrete"),
    (["foundation", "underpinning"], "foundation repair"),
    (["addition", "adu", "remodel", "renovation", "alteration", "interior work", "kitchen", "bathroom"], "remodeling"),
    (["demolition", "demo"], "demolition"),
    (["excavation", "grading", "earthwork"], "excavation"),
    (["generator", "standby"], "generator"),
    (["ev charger", "electric vehicle"], "ev charger"),
    (["waterproof", "drainage", "moisture"], "waterproofing"),
    (["painting", "paint"], "painting"),
    (["flooring", "floor"], "flooring"),
    (["garage door"], "garage door"),
    (["mold", "asbestos", "remediat", "abatement"], "mold remediation"),
    (["security", "alarm", "camera"], "security"),
    (["smart home", "automation"], "smart home"),
    (["landscaping", "irrigation", "sprinkler"], "landscaping"),
    (["tree", "arborist"], "tree service"),
    (["paving", "asphalt", "blacktop"], "paving"),
    (["masonry", "brick", "stone", "tuckpointing"], "masonry"),
    (["radon"], "radon mitigation"),
]


def _map_permit_to_industry(permit_type: str, description: str) -> str | None:
    combined = f"{permit_type} {description}".lower()
    for keywords, industry in PERMIT_TO_INDUSTRY:
        if any(kw in combined for kw in keywords):
            return industry
    return None


def _build_address(row: dict, address_fields: list[str]) -> str | None:
    parts = [str(row.get(f, "") or "").strip() for f in address_fields]
    addr = " ".join(p for p in parts if p)
    return addr if addr else None


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%Y %H:%M:%S %p"):
        try:
            return datetime.strptime(date_str[:19], fmt[:len(fmt)])
        except ValueError:
            continue
    return None


class BuildingPermitScraper(BaseScraper):
    """
    Pulls recent building permits from city open data APIs.
    Returns consumer-type leads (homeowners, not businesses).
    Only pulls permits from the last 90 days to ensure hot intent.
    """

    # How far back to look — 90 days ensures leads are actively in-market
    LOOKBACK_DAYS = 90

    def scrape(self, industry: str, city: str, state: str, max_results: int = 200) -> list[ScrapedLead]:
        city_lower = city.lower().strip()
        state_upper = state.upper().strip()

        config = None
        for (cfg_city, cfg_state), cfg in PERMIT_ENDPOINTS.items():
            if cfg_state == state_upper and cfg_city in city_lower:
                config = cfg
                break

        if not config:
            return []

        return self._fetch_permits(config, industry, max_results)

    def _fetch_permits(self, config: dict, target_industry: str, max_results: int) -> list[ScrapedLead]:
        domain = config["domain"]
        resource = config["resource"]
        city_name = config["city_name"]
        state = config["state"]

        name_f = config["name_field"]
        addr_fields = config["address_fields"]
        zip_f = config["zip_field"]
        type_f = config["type_field"]
        desc_f = config["desc_field"]
        date_f = config["date_field"]

        cutoff = (datetime.now() - timedelta(days=self.LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")
        leads = []
        offset = 0
        limit = 200

        # Use $where to only fetch recent permits
        where = f"{date_f} >= '{cutoff}'"

        with httpx.Client(timeout=25) as client:
            while len(leads) < max_results:
                url = f"https://{domain}/resource/{resource}.json"
                params = {
                    "$limit": limit,
                    "$offset": offset,
                    "$where": where,
                    "$order": f"{date_f} DESC",
                }

                try:
                    resp = client.get(url, params=params)
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    print(f"[building-permits] {city_name} HTTP error: {e}")
                    break

                rows = resp.json()
                if not rows:
                    break

                for row in rows:
                    permit_type = str(row.get(type_f, "") or "")
                    description = str(row.get(desc_f, "") or "")
                    mapped = _map_permit_to_industry(permit_type, description)
                    if not mapped:
                        continue

                    # Filter to requested industry
                    if target_industry.lower() not in mapped and mapped not in target_industry.lower():
                        continue

                    # Get homeowner/applicant name
                    contact_name = str(row.get(name_f, "") or "").strip()
                    if not contact_name:
                        continue
                    # Skip clearly commercial applicants
                    if any(kw in contact_name.lower() for kw in ["llc", "inc.", "corp", "ltd", "roofing co", "construction"]):
                        continue

                    address = _build_address(row, addr_fields)
                    if not address:
                        continue

                    zip_code = str(row.get(zip_f, "") or "").strip()[:10] or None
                    full_address = f"{address}, {city_name}, {state}"
                    if zip_code:
                        full_address += f" {zip_code}"

                    # Parse permit date for years_in_business signal (permit age)
                    permit_date = _parse_date(str(row.get(date_f, "") or ""))
                    days_old = (datetime.now() - permit_date).days if permit_date else 999

                    # Use address + name as dedup key
                    dedup_key = f"permit:{state}:{re.sub(r'[^a-z0-9]', '', full_address.lower()[:60])}"

                    leads.append(ScrapedLead(
                        business_name=contact_name,  # homeowner name
                        industry=mapped,
                        city=city_name,
                        state=state,
                        website=None,
                        phone=None,
                        zip_code=zip_code,
                        full_address=full_address,
                        contact_name=contact_name,
                        source_url=dedup_key,
                        source="building_permits",
                        lead_type="consumer",  # THIS IS THE KEY — consumer intent
                        years_in_business=days_old,  # repurposed: days since permit issued
                    ))

                if len(rows) < limit:
                    break
                offset += limit
                time.sleep(0.3)

        return leads[:max_results]
