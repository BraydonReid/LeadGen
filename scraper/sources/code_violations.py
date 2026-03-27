"""
Code Enforcement Violations Scraper — Dallas, Houston, Austin TX.

Pulls active code violation cases from city open data portals (Socrata/ArcGIS).
These are properties with a legal obligation to fix a specific issue,
making them the hottest possible intent leads for the matching contractor.

Why this is gold:
  - A property cited for "damaged roof" MUST hire a roofer — it's legally required
  - Homeowner has a deadline, not just a preference
  - Address + violation type = targeted lead for the exact right contractor
  - No competitor has this data

Supported cities (all free, public records):
  - Dallas TX: dallasopendata.com (Socrata)
  - Houston TX: data.houstontx.gov (Socrata)
  - Austin TX: data.austintexas.gov (Socrata)

Run standalone:
    python sources/code_violations.py

Or import:
    from sources.code_violations import CodeViolationScraper
    scraper = CodeViolationScraper()
    leads = scraper.run(days_back=30, max_results=500)
"""

import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from sources.base import BaseScraper, ScrapedLead

# Code violation endpoints — all Socrata, free, no key
VIOLATION_ENDPOINTS = {
    ("dallas", "TX"): {
        "domain": "www.dallasopendata.com",
        "resource": "aq3b-mdjb",  # Code Enforcement Cases dataset
        "address_field": "violation_address",
        "violation_field": "violation_description",
        "date_field": "case_opened_date",
        "order_field": "case_opened_date",
        "zip_field": "zip_code",
        "city_name": "Dallas",
    },
    ("houston", "TX"): {
        "domain": "data.houstontx.gov",
        "resource": "m7nd-4s3n",  # Houston Code Enforcement dataset
        "address_field": "address",
        "violation_field": "violation_description",
        "date_field": "case_open_date",
        "order_field": "case_open_date",
        "zip_field": "zip_code",
        "city_name": "Houston",
    },
    ("austin", "TX"): {
        "domain": "data.austintexas.gov",
        "resource": "5rzy-b2ik",  # Austin Code Cases dataset
        "address_field": "address",
        "violation_field": "violation_description",
        "date_field": "case_opened_date",
        "order_field": "case_opened_date",
        "zip_field": "zip",
        "city_name": "Austin",
    },
}

# Map violation description keywords → contractor industry
VIOLATION_TO_INDUSTRY: list[tuple[list[str], str]] = [
    (["roof", "shingle", "fascia", "soffit", "gutter"], "roofing"),
    (["fence", "fencing", "wall"], "fencing"),
    (["foundation", "structural", "slab", "pier"], "foundation repair"),
    (["siding", "exterior cladding", "stucco"], "siding"),
    (["window", "glass", "broken window"], "windows"),
    (["plumb", "drain", "sewage", "water leak", "water damage"], "plumbing"),
    (["electrical", "wiring", "panel"], "electrician"),
    (["hvac", "air condition", "heating"], "hvac"),
    (["landscaping", "overgrown", "weeds", "lawn", "vegetation", "tree"], "landscaping"),
    (["painting", "paint", "peeling", "faded"], "painting"),
    (["junk", "debris", "trash", "accumulation", "inoperable vehicle"], "junk removal"),
    (["concrete", "driveway", "sidewalk", "cracking"], "concrete"),
    (["mold", "moisture", "water intrusion"], "waterproofing"),
    (["pool", "swimming pool"], "pool service"),
    (["insulation", "weatherization"], "insulation"),
]


def _map_violation_to_industry(description: str) -> str | None:
    desc_lower = description.lower()
    for keywords, industry in VIOLATION_TO_INDUSTRY:
        if any(kw in desc_lower for kw in keywords):
            return industry
    return None


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str[:19], fmt[:len(fmt)])
        except ValueError:
            continue
    return None


class CodeViolationScraper(BaseScraper):
    """
    Pulls active code enforcement violations from Texas city open data portals.
    Returns consumer-intent leads — properties with legal obligation to fix an issue.
    """

    LOOKBACK_DAYS = 60  # violations opened in the last 60 days

    def scrape(self, industry: str, city: str, state: str, max_results: int = 200) -> list[ScrapedLead]:
        """Standard BaseScraper interface — routes to the right city endpoint."""
        city_lower = city.lower().strip()
        for (cfg_city, cfg_state), config in VIOLATION_ENDPOINTS.items():
            if cfg_state == state.upper() and cfg_city in city_lower:
                return self._fetch_violations(config, industry, max_results)
        return []

    def run(self, days_back: int = LOOKBACK_DAYS, max_results: int = 500) -> list[ScrapedLead]:
        """Standalone mode: fetch from all supported cities."""
        all_leads = []
        per_city = max(50, max_results // len(VIOLATION_ENDPOINTS))
        for (city, state), config in VIOLATION_ENDPOINTS.items():
            city_leads = self._fetch_violations(config, industry=None, max_results=per_city, days_back=days_back)
            all_leads.extend(city_leads)
            print(f"[code-violations] {config['city_name']}: {len(city_leads)} leads")
        return all_leads[:max_results]

    def _fetch_violations(
        self,
        config: dict,
        industry: str | None,
        max_results: int,
        days_back: int = LOOKBACK_DAYS,
    ) -> list[ScrapedLead]:
        domain = config["domain"]
        resource = config["resource"]
        city_name = config["city_name"]
        address_f = config["address_field"]
        violation_f = config["violation_field"]
        date_f = config.get("date_field")
        order_f = config.get("order_field")
        zip_f = config.get("zip_field")

        cutoff = datetime.now() - timedelta(days=days_back)
        cutoff_str = cutoff.strftime("%Y-%m-%dT00:00:00")

        leads = []
        offset = 0
        limit = 200
        max_pages = 15

        with httpx.Client(timeout=25) as client:
            pages = 0
            while len(leads) < max_results and pages < max_pages:
                url = f"https://{domain}/resource/{resource}.json"
                params = {"$limit": limit, "$offset": offset}
                if order_f:
                    params["$order"] = f"{order_f} DESC"
                if date_f:
                    params["$where"] = f"{date_f} >= '{cutoff_str}'"

                try:
                    resp = client.get(url, params=params)
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    print(f"[code-violations] {city_name} HTTP error: {e}")
                    break

                rows = resp.json()
                if not rows:
                    break

                for row in rows:
                    violation_desc = str(row.get(violation_f, "") or "").strip()
                    if not violation_desc:
                        continue

                    mapped_industry = _map_violation_to_industry(violation_desc)
                    if not mapped_industry:
                        continue

                    # Filter to requested industry if specified
                    if industry and industry.lower() not in mapped_industry and mapped_industry not in industry.lower():
                        continue

                    address = str(row.get(address_f, "") or "").strip()
                    if not address:
                        continue

                    zip_code = str(row.get(zip_f, "") or "").strip()[:10] if zip_f else None
                    full_address = f"{address}, {city_name}, TX"
                    if zip_code:
                        full_address += f" {zip_code}"

                    violation_date = _parse_date(str(row.get(date_f, "") or "")) if date_f else None
                    days_old = (datetime.now() - violation_date).days if violation_date else 999

                    dedup_key = f"violation:{re.sub(r'[^a-z0-9]', '', full_address.lower()[:60])}"

                    # Code violations get a slightly higher quality boost — these are urgent
                    leads.append(ScrapedLead(
                        business_name=address,       # property address
                        industry=mapped_industry,
                        city=city_name,
                        state="TX",
                        phone=None,
                        email=None,
                        website=None,
                        zip_code=zip_code,
                        full_address=full_address,
                        contact_name=violation_desc[:100],  # violation description as contact_name field (informational)
                        source_url=dedup_key,
                        source="code_violations",
                        lead_type="consumer",        # legal obligation = highest possible intent
                        years_in_business=days_old,  # repurposed: days since violation opened
                    ))

                pages += 1
                if len(rows) < limit:
                    break
                offset += limit
                time.sleep(0.3)

        return leads[:max_results]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape code enforcement violations for TX cities")
    parser.add_argument("--days", type=int, default=60, help="Days back to look")
    parser.add_argument("--max", type=int, default=500, help="Max leads to fetch")
    parser.add_argument("--dry-run", action="store_true", help="Print without saving to DB")
    args = parser.parse_args()

    scraper = CodeViolationScraper()
    leads = scraper.run(days_back=args.days, max_results=args.max)

    if args.dry_run:
        for lead in leads[:20]:
            print(f"  {lead.city}: {lead.business_name[:50]} | {lead.industry} | {lead.contact_name[:60] if lead.contact_name else ''}")
        print(f"  … ({len(leads)} total)")
        sys.exit(0)

    from database import SessionLocal
    from dedup import already_exists
    from models import Lead

    def _quality(s: ScrapedLead) -> int:
        score = 10  # address always present
        days = s.years_in_business or 999
        if days <= 7: score += 20   # very recent violation = urgent
        elif days <= 30: score += 15
        elif days <= 60: score += 10
        return min(100, score)

    session = SessionLocal()
    saved = 0
    try:
        for s in leads:
            if already_exists(session, s.source_url, s.business_name, None, None, s.state):
                continue
            db_lead = Lead(
                business_name=s.business_name,
                industry=s.industry,
                city=s.city,
                state=s.state,
                phone=None,
                email=None,
                website=None,
                source_url=s.source_url,
                zip_code=s.zip_code,
                full_address=s.full_address,
                contact_name=s.contact_name,
                quality_score=_quality(s),
                source=s.source,
                lead_type=s.lead_type,
                years_in_business=s.years_in_business,
            )
            session.add(db_lead)
            saved += 1
        session.commit()
        print(f"[code-violations] Saved {saved} leads to database")
    except Exception as e:
        session.rollback()
        print(f"[code-violations] DB error: {e}")
    finally:
        session.close()
