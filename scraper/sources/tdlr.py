"""
Texas Department of Licensing & Regulation (TDLR) Scraper.

Pulls state-licensed contractor businesses from the Texas Open Data Portal.
Resource: https://data.texas.gov/resource/7358-krk7.json  (949,000+ records)

Only license types with business address data are included:
  Electrical Contractor    — 12,373 TX records with address + phone
  Water Well Driller/Pump Installer — 1,094 TX records with address + phone

Other TDLR license types (A/C Contractor, Master Electrician, etc.) do not
publish business addresses in this dataset and are therefore excluded.

lead_type is set to "business" — state-licensed Texas contractor businesses.
"""

import re
from datetime import datetime

import httpx

from sources.base import BaseScraper, ScrapedLead
from utils import smart_title

TDLR_URL = "https://data.texas.gov/resource/7358-krk7.json"

# Keyword patterns in search term → TDLR license types that have address data
INDUSTRY_TO_LICENSE_TYPES: list[tuple[list[str], list[str]]] = [
    (
        ["electric", "electrician", "wiring", "wireman", "lineman"],
        ["Electrical Contractor"],
    ),
    (
        ["well pump", "well drill", "water well", "pump install", "well service"],
        ["Water Well Driller/Pump Installer"],
    ),
]

_LICENSE_TO_INDUSTRY: dict[str, str] = {
    "Electrical Contractor": "electrician",
    "Water Well Driller/Pump Installer": "well pump",
}


def _parse_city_state_zip(city_state_zip: str) -> tuple[str, str, str]:
    """Parse 'HOUSTON TX 77001' or 'SAN ANTONIO TX 78201-1234' into parts."""
    parts = city_state_zip.strip().split()
    if len(parts) < 2:
        return "", "", ""
    if len(parts) >= 3:
        state = parts[-2]
        zip_code = parts[-1].split("-")[0]  # drop zip+4 extension
        city = " ".join(parts[:-2])
    else:
        state = parts[-1]
        zip_code = ""
        city = parts[0]
    return city, state, zip_code


def _parse_expiration(date_str: str) -> datetime | None:
    """Parse 'MM/DD/YYYY' expiration date field."""
    try:
        return datetime.strptime(date_str.strip(), "%m/%d/%Y")
    except (ValueError, AttributeError):
        return None


class TDLRScraper(BaseScraper):
    """
    Scrapes state-licensed electrical contractor and water-well businesses
    from the TDLR dataset on data.texas.gov.  Returns business-type leads.
    Texas-only — returns [] for any state other than TX.
    """

    def scrape(
        self, industry: str, city: str, state: str, max_results: int = 200
    ) -> list[ScrapedLead]:
        if state.upper() != "TX":
            return []

        industry_lower = industry.lower()
        license_types: list[str] = []
        for keywords, types in INDUSTRY_TO_LICENSE_TYPES:
            if any(kw in industry_lower for kw in keywords):
                license_types.extend(types)

        if not license_types:
            return []

        leads: list[ScrapedLead] = []
        for lic_type in set(license_types):
            if len(leads) >= max_results:
                break
            batch = self._fetch_tdlr(lic_type, city, max_results - len(leads))
            leads.extend(batch)

        return leads[:max_results]

    # ------------------------------------------------------------------

    def _fetch_tdlr(
        self, license_type: str, city: str, max_results: int
    ) -> list[ScrapedLead]:
        city_upper = city.upper().strip() if city else ""

        # Base WHERE: has address, licensed in Texas
        base_where = (
            f"license_type='{license_type}'"
            " AND business_address_line1 IS NOT NULL"
            " AND business_city_state_zip LIKE '% TX %'"
        )
        # Narrow to city if provided
        city_clause = (
            f" AND upper(business_city_state_zip) LIKE '{city_upper} TX%'"
            if city_upper
            else ""
        )
        where = base_where + city_clause

        leads: list[ScrapedLead] = []
        offset = 0
        limit = 500
        max_pages = 10

        with httpx.Client(timeout=30) as client:
            for _ in range(max_pages):
                if len(leads) >= max_results:
                    break
                params = {
                    "$limit": limit,
                    "$offset": offset,
                    "$where": where,
                    "$order": "license_number DESC",
                }
                try:
                    resp = client.get(TDLR_URL, params=params)
                    resp.raise_for_status()
                    rows = resp.json()
                except Exception as e:
                    print(f"[tdlr] {license_type}/{city} error: {e}")
                    break

                if not rows:
                    break

                for row in rows:
                    lead = self._parse_row(row, license_type)
                    if lead:
                        leads.append(lead)

                if len(rows) < limit:
                    break
                offset += limit

        return leads[:max_results]

    # ------------------------------------------------------------------

    def _parse_row(self, row: dict, license_type: str) -> ScrapedLead | None:
        business_name = (row.get("business_name") or "").strip()
        if not business_name:
            return None

        address_line1 = (row.get("business_address_line1") or "").strip()
        if not address_line1:
            return None

        city_state_zip = (row.get("business_city_state_zip") or "").strip()
        city, state, zip_code = _parse_city_state_zip(city_state_zip)
        if state != "TX":
            return None

        # Skip expired licenses (only active/future licenses are useful leads)
        exp_date = _parse_expiration(row.get("license_expiration_date_mmddccyy", ""))
        if exp_date and exp_date < datetime.now():
            return None

        # Phone: prefer business number, fall back to owner number
        raw_phone = (
            row.get("business_telephone") or row.get("owner_telephone") or ""
        ).strip()
        digits = re.sub(r"\D", "", raw_phone)
        phone = digits[:10] if len(digits) >= 10 else None

        owner_name = (row.get("owner_name") or "").strip()

        full_address = f"{address_line1}, {city.title()}, TX"
        if zip_code:
            full_address += f" {zip_code}"

        industry = _LICENSE_TO_INDUSTRY.get(license_type, license_type.lower())
        dedup_key = (
            "tdlr:TX:"
            + re.sub(r"[^a-z0-9]", "", (business_name + address_line1).lower()[:60])
        )

        return ScrapedLead(
            business_name=smart_title(business_name),
            industry=industry,
            city=smart_title(city),
            state="TX",
            website=None,
            phone=phone,
            zip_code=zip_code or None,
            full_address=full_address,
            contact_name=smart_title(owner_name) if owner_name else None,
            source_url=dedup_key,
            source="tdlr",
            lead_type="business",
            years_in_business=None,
        )
