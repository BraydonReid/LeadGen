"""
ArcGIS REST Building Permit Scraper.

Covers cities that publish permit data via ArcGIS FeatureServer/MapServer REST APIs.
All free, no API key required.

Supported cities:
  Raleigh NC    — services.arcgis.com  (parcel owner name — best homeowner data)
  Minneapolis MN — services.arcgis.com
  Nashville TN  — services2.arcgis.com
  Denver CO     — services1.arcgis.com (residential construction)
  Tempe AZ      — services.arcgis.com
  Fort Worth TX — mapit.fortworthtexas.gov MapServer (live daily updates!)

ArcGIS dates are returned as epoch milliseconds — handled automatically.
lead_type is set to "consumer" — same premium pricing as Socrata/CKAN permits.
"""

import re
import time
from datetime import datetime, timedelta, timezone

import httpx

from sources.base import BaseScraper, ScrapedLead
from sources.building_permits import _map_permit_to_industry

# ---------------------------------------------------------------------------
# Endpoint configs
# ---------------------------------------------------------------------------

ARCGIS_ENDPOINTS: dict[tuple[str, str], dict] = {
    ("raleigh", "NC"): {
        "url": (
            "https://services.arcgis.com/v400IkDOw1ad7Yad/arcgis/rest/services"
            "/Building_Permits/FeatureServer/0/query"
        ),
        "name_field": "parcelownername",
        "fallback_name_field": "contractorcompanyname",
        "address_fields": ["originaladdress1"],
        "zip_field": "originalzip",
        "type_field": "permittypemapped",
        "desc_field": "proposedworkdescription",
        "date_field": "issueddate",
        "city_name": "Raleigh",
        "state": "NC",
    },
    ("minneapolis", "MN"): {
        "url": (
            "https://services.arcgis.com/afSMGVsC7QlRK1kZ/arcgis/rest/services"
            "/CCS_Permits/FeatureServer/0/query"
        ),
        "name_field": "applicantName",
        "fallback_name_field": "fullName",
        "address_fields": ["applicantAddress1"],
        "zip_field": None,
        "type_field": "permitType",
        "desc_field": "workType",
        "date_field": "issueDate",
        "city_name": "Minneapolis",
        "state": "MN",
    },
    ("nashville", "TN"): {
        "url": (
            "https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services"
            "/Building_Permits_Issued_2/FeatureServer/0/query"
        ),
        "name_field": "Contact",
        "address_fields": ["Address"],
        "zip_field": "ZIP",
        "type_field": "Permit_Type_Description",
        "desc_field": "Purpose",
        "date_field": "Date_Issued",
        "city_name": "Nashville",
        "state": "TN",
    },
    # Louisville KY — dataset last updated 2019; removed until a live endpoint is confirmed.
    ("denver", "CO"): {
        "url": (
            "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services"
            "/ODC_DEV_RESIDENTIALCONSTPERMIT_P/FeatureServer/316/query"
        ),
        "name_field": "CONTRACTOR_NAME",
        "address_fields": ["ADDRESS"],
        "zip_field": None,
        "type_field": "CLASS",
        "desc_field": "CLASS",
        "date_field": "DATE_ISSUED",
        "city_name": "Denver",
        "state": "CO",
    },
    ("tempe", "AZ"): {
        "url": (
            "https://services.arcgis.com/lQySeXwbBg53XWDi/arcgis/rest/services"
            "/building_permits/FeatureServer/0/query"
        ),
        "name_field": "ContractorCompanyName",
        "address_fields": ["OriginalAddress1"],
        "zip_field": "OriginalZip",
        "type_field": "PermitTypeDesc",
        "desc_field": "Description",
        "date_field": "IssuedDateDtm",
        "city_name": "Tempe",
        "state": "AZ",
    },
    # Fort Worth TX — live daily permit data, verified 2026-03-19
    # Note: epoch-ms date filter triggers 400; the scraper's 1=1 fallback handles this.
    # Data is ordered DESC so newest records are processed first — still efficient.
    ("fort worth", "TX"): {
        "url": (
            "https://mapit.fortworthtexas.gov/ags/rest/services"
            "/CIVIC/Permits/MapServer/0/query"
        ),
        "name_field": "Owner_Full_Name",
        "address_fields": ["Address"],
        "zip_field": "Zip_Code",
        "type_field": "Permit_Type",
        "desc_field": "B1_WORK_DESC",
        "date_field": "File_Date",
        "city_name": "Fort Worth",
        "state": "TX",
    },
}
# Las Vegas NV — mapdata.lasvegasnevada.gov MapServer returns data from 2004; removed until a live endpoint is confirmed.

COMMERCIAL_KEYWORDS = ["llc", "inc.", " inc", "corp", "ltd", "roofing co", "construction",
                       "l.l.c", "properties", "realty", "holdings", "partners",
                       " lp", " llp", " builders", " homes", " development", " group",
                       "sports auth", "d.r. horton", "drh-", "dr horton",
                       " trust", " investments", "real estate", " develop",
                       "lennar", "pulte", "kb home", "meritage", "nvr "]


def _parse_arcgis_date(value) -> datetime | None:
    """ArcGIS returns dates as epoch milliseconds (int) or ISO strings."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and value > 0:
        try:
            return datetime.fromtimestamp(value / 1000)
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(value, str) and value:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(value[:19], fmt)
            except ValueError:
                continue
    return None


def _build_address(row: dict, address_fields: list[str]) -> str | None:
    parts = [str(row.get(f, "") or "").strip() for f in address_fields]
    addr = " ".join(p for p in parts if p)
    return addr if addr else None


def _is_commercial(name: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in COMMERCIAL_KEYWORDS)


class ArcGISPermitScraper(BaseScraper):
    """
    Scrapes building permit data from ArcGIS FeatureServer/MapServer REST APIs.
    Returns consumer-type leads (homeowners/contractors actively doing work).
    """

    LOOKBACK_DAYS = 90

    def scrape(self, industry: str, city: str, state: str, max_results: int = 200) -> list[ScrapedLead]:
        city_lower = city.lower().strip()
        state_upper = state.upper().strip()

        config = None
        for (cfg_city, cfg_state), cfg in ARCGIS_ENDPOINTS.items():
            if cfg_state == state_upper and cfg_city in city_lower:
                config = cfg
                break

        if not config:
            return []

        return self._fetch_arcgis(config, industry, max_results)

    def _fetch_arcgis(self, config: dict, target_industry: str, max_results: int) -> list[ScrapedLead]:
        url = config["url"]
        city_name = config["city_name"]
        state = config["state"]

        name_f = config["name_field"]
        fallback_name_f = config.get("fallback_name_field")
        addr_fields = config["address_fields"]
        zip_f = config["zip_field"]
        type_f = config["type_field"]
        desc_f = config["desc_field"]
        date_f = config["date_field"]

        # Build date WHERE clause using epoch ms (works for all ArcGIS date fields)
        cutoff_dt = datetime.now() - timedelta(days=self.LOOKBACK_DAYS)
        cutoff_epoch_ms = int(cutoff_dt.timestamp() * 1000)
        where_clause = f"{date_f} >= {cutoff_epoch_ms}"

        leads: list[ScrapedLead] = []
        offset = 0
        limit = 200
        max_pages = 15

        headers = {"User-Agent": "Mozilla/5.0 (compatible; LeadGenBot/1.0)"}
        with httpx.Client(timeout=45, headers=headers) as client:
            for _ in range(max_pages):
                if len(leads) >= max_results:
                    break

                params = {
                    "where": where_clause,
                    "outFields": "*",
                    "resultRecordCount": limit,
                    "resultOffset": offset,
                    "orderByFields": f"{date_f} DESC",
                    "f": "json",
                }
                data = None
                for attempt in range(2):
                    try:
                        resp = client.get(url, params=params)
                        resp.raise_for_status()
                        data = resp.json()
                        break
                    except Exception as e:
                        if attempt == 1:
                            print(f"[arcgis-permits] {city_name} error: {e}")
                        time.sleep(5)
                if data is None:
                    break

                # ArcGIS returns an error dict if the query fails (e.g. wrong field name)
                if "error" in data:
                    # Retry without date filter — fall back to unfiltered + local check
                    params["where"] = "1=1"
                    try:
                        resp = client.get(url, params=params)
                        data = resp.json()
                    except Exception:
                        break

                features = data.get("features", [])
                if not features:
                    break

                for feat in features:
                    row = feat.get("attributes", {})

                    permit_type = str(row.get(type_f, "") or "")
                    description = str(row.get(desc_f, "") or "")
                    mapped = _map_permit_to_industry(permit_type, description)
                    if not mapped:
                        continue
                    if target_industry.lower() not in mapped and mapped not in target_industry.lower():
                        continue

                    # Name
                    contact_name = str(row.get(name_f, "") or "").strip()
                    if not contact_name and fallback_name_f:
                        contact_name = str(row.get(fallback_name_f, "") or "").strip()
                    if not contact_name:
                        continue
                    if _is_commercial(contact_name):
                        continue

                    # Address
                    address = _build_address(row, addr_fields)
                    if not address:
                        continue

                    zip_code = str(row.get(zip_f, "") or "").strip()[:10] if zip_f else None
                    full_address = f"{address}, {city_name}, {state}"
                    if zip_code:
                        full_address += f" {zip_code}"

                    # Date
                    permit_date = _parse_arcgis_date(row.get(date_f))
                    days_old = (datetime.now() - permit_date).days if permit_date else 999
                    if permit_date and days_old > self.LOOKBACK_DAYS:
                        continue

                    dedup_key = f"permit:{state}:{re.sub(r'[^a-z0-9]', '', full_address.lower()[:60])}"

                    leads.append(ScrapedLead(
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
                    ))

                # ArcGIS signals last page via exceededTransferLimit=False or fewer results
                if not data.get("exceededTransferLimit", False) and len(features) < limit:
                    break
                offset += limit
                time.sleep(0.3)

        return leads[:max_results]
