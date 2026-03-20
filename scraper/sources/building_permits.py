"""
Building Permit Consumer Intent Scraper — Socrata endpoints.

Pulls from city/county open data APIs (Socrata — no API key required).
Building permits are the highest-quality consumer intent signal available:
  - A homeowner who just pulled a ROOFING permit IS currently replacing their roof
  - They need a contractor RIGHT NOW
  - We know their exact address, permit type, and issue date

Supported cities (all free, no key):
  Chicago IL, New York City NY, Seattle WA,
  Dallas TX, Honolulu HI, Austin TX

See also: ckan_permits.py (Boston, San Antonio, San Jose, Pittsburgh, Philadelphia)
         arcgis_permits.py (Raleigh, Minneapolis, Nashville, Louisville, Denver, Tempe, Las Vegas)

lead_type is set to "consumer" — these leads command 1.5× price premium.
"""

import re
import time
from datetime import datetime, timedelta

import httpx

from sources.base import BaseScraper, ScrapedLead

# City permit endpoints (Socrata — all free, no key needed)
# Field names verified against live APIs. Note: some cities have no date field
# in their dataset; the scraper handles this by skipping the date filter.
PERMIT_ENDPOINTS = {
    ("chicago", "IL"): {
        "domain": "data.cityofchicago.org",
        "resource": "ydr8-5enu",
        "name_field": "contact_1_name",
        "address_fields": ["street_number", "street_direction", "street_name"],
        "zip_field": "contact_1_zipcode",
        "type_field": "permit_type",
        "desc_field": "work_description",
        "date_field": "issue_date",
        "order_field": "issue_date",   # enables $order DESC to get newest permits first
        "city_name": "Chicago",
        "state": "IL",
    },
    ("new york city", "NY"): {
        "domain": "data.cityofnewyork.us",
        "resource": "rbx6-tga4",
        "name_field": "owner_name",
        "address_fields": ["house_no", "street_name"],
        "zip_field": "zip_code",
        "type_field": "work_type",
        "desc_field": "job_description",
        "date_field": None,            # no date field in this dataset; no date filter applied
        "city_name": "New York City",
        "state": "NY",
    },
    ("seattle", "WA"): {
        "domain": "data.seattle.gov",
        "resource": "76t5-zqzr",
        "name_field": "contractorcompanyname",
        "address_fields": ["originaladdress1"],
        "zip_field": "originalzip",
        "type_field": "permittypemapped",
        "desc_field": "description",
        "date_field": None,            # no date field in this dataset; no date filter applied
        "city_name": "Seattle",
        "state": "WA",
    },
    ("dallas", "TX"): {
        "domain": "www.dallasopendata.com",
        "resource": "e7gq-4sah",
        "name_field": "contractor",
        "address_fields": ["street_address"],
        "zip_field": "zip_code",
        "type_field": "permit_type",
        "desc_field": "work_description",
        "date_field": "issued_date",
        "order_field": "issued_date",
        "city_name": "Dallas",
        "state": "TX",
    },
    ("honolulu", "HI"): {
        "domain": "data.honolulu.gov",
        "resource": "4vab-c87q",
        "name_field": "applicant",
        "address_fields": ["address"],
        "zip_field": None,
        "type_field": "proposeduse",
        "desc_field": "proposeduse",
        # Honolulu uses boolean Y/N fields for work type instead of a description string.
        # extra_desc_fields: field names whose value=="Y" get appended to the description
        # so _map_permit_to_industry can match "electricalwork" → electrician, "solar" → solar, etc.
        "extra_desc_fields": [
            "electricalwork", "plumbingwork", "solar", "fence", "pool",
            "repair", "addition", "alteration", "demolition", "newbuilding",
        ],
        "date_field": "issuedate",
        "order_field": "issuedate",
        "city_name": "Honolulu",
        "state": "HI",
    },
    # Austin TX — individual licensed contractor names + homeowner residential addresses
    ("austin", "TX"): {
        "domain": "data.austintexas.gov",
        "resource": "3syk-w9eu",
        "name_field": "contractor_full_name",
        "fallback_name_field": "contractor_company_name",
        "address_fields": ["original_address1"],
        "zip_field": "original_zip",
        "type_field": "permit_type_desc",
        "desc_field": "description",
        "date_field": "issue_date",
        "order_field": "issue_date",
        "city_name": "Austin",
        "state": "TX",
    },
}
# Fort Worth TX — Socrata resource qy5k-jz7m last updated 2015; removed until a live dataset is found.

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
        date_f = config["date_field"]           # None means no date field in dataset
        order_f = config.get("order_field")     # Optional: sort newest-first for efficiency
        extra_desc_f = config.get("extra_desc_fields", [])  # Boolean Y/N fields (Honolulu)

        cutoff_days = self.LOOKBACK_DAYS
        leads = []
        offset = 0
        limit = 200
        max_pages = 15  # cap at 3,000 records scanned to avoid runaway pagination

        with httpx.Client(timeout=25) as client:
            pages_scanned = 0
            while len(leads) < max_results and pages_scanned < max_pages:
                url = f"https://{domain}/resource/{resource}.json"
                params = {
                    "$limit": limit,
                    "$offset": offset,
                }
                # Sort newest-first when the date field is known — avoids scanning old records
                if order_f:
                    params["$order"] = f"{order_f} DESC"

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
                    # Honolulu-style datasets use boolean Y/N fields for work type;
                    # append the field name itself when value is "Y" so keyword
                    # matching works: electricalwork=Y → "electricalwork" in combined
                    if extra_desc_f:
                        extra = " ".join(
                            f for f in extra_desc_f
                            if str(row.get(f, "")).strip().upper() == "Y"
                        )
                        description = f"{description} {extra}".strip()
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
                    if any(kw in contact_name.lower() for kw in ["llc", "inc.", " inc", "corp", "ltd", "roofing co", "construction", " lp", " llp", " builders", " homes", " development"]):
                        continue

                    address = _build_address(row, addr_fields)
                    if not address:
                        continue

                    zip_code = str(row.get(zip_f, "") or "").strip()[:10] or None
                    full_address = f"{address}, {city_name}, {state}"
                    if zip_code:
                        full_address += f" {zip_code}"

                    # Parse permit date for years_in_business signal (permit age)
                    permit_date = _parse_date(str(row.get(date_f, "") or "")) if date_f else None
                    days_old = (datetime.now() - permit_date).days if permit_date else 999

                    # Skip permits older than the lookback window
                    # If no date field exists (days_old=999 from None), allow through
                    if permit_date and days_old > cutoff_days:
                        continue

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

                pages_scanned += 1
                if len(rows) < limit:
                    break
                offset += limit
                time.sleep(0.3)

        return leads[:max_results]
