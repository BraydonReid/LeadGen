"""
CKAN + Carto Building Permit Scraper.

Covers cities that publish permit data via CKAN open-data portals or Carto SQL,
rather than Socrata.  All free, no API key required.

Supported cities:
  San Antonio TX — data.sanantonio.gov (CKAN) — Texas primary
  Boston MA    — data.boston.gov       (CKAN)
  San Jose CA  — data.sanjoseca.gov    (CKAN)
  Pittsburgh PA — data.wprdc.org       (CKAN)
  Philadelphia PA — phl.carto.com      (Carto SQL)

lead_type is set to "consumer" — same premium pricing as Socrata permits.
"""

import re
import time
from datetime import datetime, timedelta

import httpx

from sources.base import BaseScraper, ScrapedLead
from sources.building_permits import PERMIT_TO_INDUSTRY, _map_permit_to_industry, _parse_date

# ---------------------------------------------------------------------------
# Endpoint configs
# ---------------------------------------------------------------------------

CKAN_ENDPOINTS: dict[tuple[str, str], dict] = {
    ("boston", "MA"): {
        "platform": "ckan",
        "domain": "data.boston.gov",
        "resource_id": "6ddcd912-32a0-43df-9908-63574f8c7e77",
        "name_field": "applicant",
        "address_fields": ["address"],
        "zip_field": "zip",
        "type_field": "worktype",
        "desc_field": "permittypedescr",
        "date_field": "issued_date",
        "sort_field": "issued_date",
        "city_name": "Boston",
        "state": "MA",
    },
    # San Antonio TX — new resource ID (c21106f9), updated Jan 2026 with current data
    ("san antonio", "TX"): {
        "platform": "ckan",
        "domain": "data.sanantonio.gov",
        "resource_id": "c21106f9-3ef5-4f3a-8604-f992b4db7512",
        "name_field": "PRIMARY CONTACT",
        "address_fields": ["ADDRESS"],
        "zip_field": None,
        "type_field": "PERMIT TYPE",
        "desc_field": "WORK TYPE",
        "date_field": "DATE ISSUED",
        "sort_field": "DATE ISSUED",
        "city_name": "San Antonio",
        "state": "TX",
    },
    ("san jose", "CA"): {
        "platform": "ckan",
        "domain": "data.sanjoseca.gov",
        "resource_id": "761b7ae8-3be1-4ad6-923d-c7af6404a904",
        "name_field": "OWNERNAME",
        "fallback_name_field": "APPLICANT",
        "address_fields": ["gx_location"],
        "zip_field": None,
        "type_field": "SUBTYPEDESCRIPTION",
        "desc_field": "WORKDESCRIPTION",
        "date_field": "ISSUEDATE",
        "sort_field": "ISSUEDATE",
        "city_name": "San Jose",
        "state": "CA",
    },
    ("pittsburgh", "PA"): {
        "platform": "ckan",
        "domain": "data.wprdc.org",
        "resource_id": "f4d1177a-f597-4c32-8cbf-7885f56253f6",
        "name_field": "owner_name",
        "fallback_name_field": "contractor_name",
        "address_fields": ["address"],
        "zip_field": "zip_code",
        "type_field": "permit_type",
        "desc_field": "work_description",
        "date_field": "issue_date",
        "sort_field": "issue_date",
        "city_name": "Pittsburgh",
        "state": "PA",
    },
    ("philadelphia", "PA"): {
        "platform": "carto",
        "domain": "phl.carto.com",
        "carto_table": "permits",
        "name_field": "opa_owner",          # property owner from OPA records
        "fallback_name_field": "contractorname",
        "address_fields": ["address"],
        "zip_field": "zip",
        "type_field": "typeofwork",
        "desc_field": "approvedscopeofwork",
        "date_field": "permitissuedate",
        "city_name": "Philadelphia",
        "state": "PA",
    },
}

COMMERCIAL_KEYWORDS = ["llc", "inc.", " inc", "corp", "ltd", "roofing co", "construction",
                       "l.l.c", "properties", "realty", "holdings", "partners",
                       " lp", " llp", " builders", " homes", " development"]


def _build_address(row: dict, address_fields: list[str]) -> str | None:
    parts = [str(row.get(f, "") or "").strip() for f in address_fields]
    addr = " ".join(p for p in parts if p)
    return addr if addr else None


def _is_commercial(name: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in COMMERCIAL_KEYWORDS)


class CKANPermitScraper(BaseScraper):
    """
    Scrapes building permit data from CKAN open-data portals and Carto SQL.
    Returns consumer-type leads (homeowners/property owners actively in-market).
    """

    LOOKBACK_DAYS = 90

    def scrape(self, industry: str, city: str, state: str, max_results: int = 200) -> list[ScrapedLead]:
        city_lower = city.lower().strip()
        state_upper = state.upper().strip()

        config = None
        for (cfg_city, cfg_state), cfg in CKAN_ENDPOINTS.items():
            if cfg_state == state_upper and cfg_city in city_lower:
                config = cfg
                break

        if not config:
            return []

        platform = config["platform"]
        if platform == "ckan":
            return self._fetch_ckan(config, industry, max_results)
        elif platform == "carto":
            return self._fetch_carto(config, industry, max_results)
        return []

    # ------------------------------------------------------------------
    # CKAN  —  GET /api/3/action/datastore_search
    # ------------------------------------------------------------------

    def _fetch_ckan(self, config: dict, target_industry: str, max_results: int) -> list[ScrapedLead]:
        domain = config["domain"]
        resource_id = config["resource_id"]
        city_name = config["city_name"]
        state = config["state"]

        name_f = config["name_field"]
        fallback_name_f = config.get("fallback_name_field")
        addr_fields = config["address_fields"]
        zip_f = config["zip_field"]
        type_f = config["type_field"]
        desc_f = config["desc_field"]
        date_f = config["date_field"]
        sort_f = config.get("sort_field")  # sort newest-first to avoid scanning stale records

        leads: list[ScrapedLead] = []
        offset = 0
        limit = 100
        max_pages = 20
        cutoff = datetime.now() - timedelta(days=self.LOOKBACK_DAYS)

        with httpx.Client(timeout=25) as client:
            for _ in range(max_pages):
                if len(leads) >= max_results:
                    break
                url = f"https://{domain}/api/3/action/datastore_search"
                params = {"resource_id": resource_id, "limit": limit, "offset": offset}
                if sort_f:
                    params["sort"] = f"{sort_f} desc"
                try:
                    resp = client.get(url, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    print(f"[ckan-permits] {city_name} error: {e}")
                    break

                records = data.get("result", {}).get("records", [])
                if not records:
                    break

                for row in records:
                    lead = self._parse_row(
                        row, name_f, fallback_name_f, addr_fields, zip_f,
                        type_f, desc_f, date_f, target_industry,
                        city_name, state, cutoff,
                    )
                    if lead:
                        leads.append(lead)

                if len(records) < limit:
                    break
                offset += limit
                time.sleep(0.3)

        return leads[:max_results]

    # ------------------------------------------------------------------
    # Carto SQL  —  GET /api/v2/sql?q=SELECT...
    # ------------------------------------------------------------------

    def _fetch_carto(self, config: dict, target_industry: str, max_results: int) -> list[ScrapedLead]:
        domain = config["domain"]
        table = config["carto_table"]
        city_name = config["city_name"]
        state = config["state"]

        name_f = config["name_field"]
        fallback_name_f = config.get("fallback_name_field")
        addr_fields = config["address_fields"]
        zip_f = config["zip_field"]
        type_f = config["type_field"]
        desc_f = config["desc_field"]
        date_f = config["date_field"]

        cutoff = datetime.now() - timedelta(days=self.LOOKBACK_DAYS)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        leads: list[ScrapedLead] = []
        offset = 0
        limit = 500
        max_pages = 10

        with httpx.Client(timeout=30) as client:
            for _ in range(max_pages):
                if len(leads) >= max_results:
                    break
                sql = (
                    f"SELECT * FROM {table} "
                    f"WHERE {date_f} >= '{cutoff_str}' "
                    f"ORDER BY {date_f} DESC "
                    f"LIMIT {limit} OFFSET {offset}"
                )
                try:
                    resp = client.get(f"https://{domain}/api/v2/sql", params={"q": sql})
                    resp.raise_for_status()
                    rows = resp.json().get("rows", [])
                except Exception as e:
                    print(f"[carto-permits] {city_name} error: {e}")
                    break

                if not rows:
                    break

                for row in rows:
                    lead = self._parse_row(
                        row, name_f, fallback_name_f, addr_fields, zip_f,
                        type_f, desc_f, date_f, target_industry,
                        city_name, state, cutoff,
                    )
                    if lead:
                        leads.append(lead)

                if len(rows) < limit:
                    break
                offset += limit
                time.sleep(0.3)

        return leads[:max_results]

    # ------------------------------------------------------------------
    # Shared row parser
    # ------------------------------------------------------------------

    def _parse_row(
        self, row: dict,
        name_f: str, fallback_name_f: str | None,
        addr_fields: list[str], zip_f: str | None,
        type_f: str, desc_f: str, date_f: str,
        target_industry: str, city_name: str, state: str,
        cutoff: datetime,
    ) -> ScrapedLead | None:

        # Industry matching
        permit_type = str(row.get(type_f, "") or "")
        description = str(row.get(desc_f, "") or "")
        mapped = _map_permit_to_industry(permit_type, description)
        if not mapped:
            return None
        if target_industry.lower() not in mapped and mapped not in target_industry.lower():
            return None

        # Name — try primary then fallback
        contact_name = str(row.get(name_f, "") or "").strip()
        if not contact_name and fallback_name_f:
            contact_name = str(row.get(fallback_name_f, "") or "").strip()
        if not contact_name:
            return None
        if _is_commercial(contact_name):
            return None

        # Address
        address = _build_address(row, addr_fields)
        if not address:
            return None

        zip_code = str(row.get(zip_f, "") or "").strip()[:10] if zip_f else None
        full_address = f"{address}, {city_name}, {state}"
        if zip_code:
            full_address += f" {zip_code}"

        # Date filter
        permit_date = _parse_date(str(row.get(date_f, "") or ""))
        if permit_date and (datetime.now() - permit_date).days > self.LOOKBACK_DAYS:
            return None

        dedup_key = f"permit:{state}:{re.sub(r'[^a-z0-9]', '', full_address.lower()[:60])}"
        days_old = (datetime.now() - permit_date).days if permit_date else 999

        return ScrapedLead(
            business_name=address,  # property address — more useful for contractors than homeowner name
            industry=mapped,
            city=city_name,
            state=state,
            website=None,
            phone=None,
            zip_code=zip_code or None,
            full_address=full_address,
            contact_name=contact_name,
            source_url=dedup_key,
            source="building_permits",
            lead_type="consumer",
            years_in_business=days_old,
        )
