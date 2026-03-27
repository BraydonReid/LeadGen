"""
Texas Secretary of State — New Business Filings Scraper.

Pulls recently formed Texas businesses from the Texas Open Data Portal
(data.texas.gov — free Socrata API, no key required).

Dataset: "Taxable Entity Search" — includes all active Texas businesses
registered with the Comptroller's Office, with formation date.

Why this matters:
  - A business formed this week is at peak buying stage for everything:
    insurance, accounting, payroll, software, banking, marketing
  - Contact info = registered agent (legal point of contact)
  - Industry can be inferred from the business name keywords

Run standalone:
    python sources/texas_sos_new_filings.py

Or import and call:
    from sources.texas_sos_new_filings import TexasSOSScraper
    scraper = TexasSOSScraper()
    leads = scraper.run(days_back=7, max_results=500)
"""

import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

# Allow running standalone from the sources/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from sources.base import BaseScraper, ScrapedLead

# Texas Open Data Portal — Active Franchise Tax Permits (Socrata)
# Field reference: https://data.texas.gov/resource/9cir-efmm.json
TXSOS_DOMAIN = "data.texas.gov"
TXSOS_RESOURCE = "9cir-efmm"

# How many days back to look for new filings
DEFAULT_LOOKBACK_DAYS = 14

# Industry keywords to infer industry from business name
NAME_TO_INDUSTRY: list[tuple[list[str], str]] = [
    (["roof", "roofer", "reroofing", "shingle"], "roofing"),
    (["solar", "photovoltaic", "pv "], "solar"),
    (["electric", "electrical", "wiring"], "electrician"),
    (["plumb", "drain", "sewer"], "plumbing"),
    (["hvac", "air condition", "heating", "cooling", "ac "], "hvac"),
    (["landscape", "lawn", "turf", "mowing"], "landscaping"),
    (["tree service", "tree trimming", "arborist", "tree removal"], "tree service"),
    (["fence", "fencing"], "fencing"),
    (["paint", "painting"], "painting"),
    (["concrete", "paving", "asphalt"], "concrete"),
    (["remodel", "renovation", "general contractor", "construction"], "remodeling"),
    (["flooring", "carpet", "tile"], "flooring"),
    (["cleaning", "maid", "janitorial"], "cleaning"),
    (["pest control", "exterminator", "termite"], "pest control"),
    (["security", "alarm", "surveillance"], "security"),
    (["insurance"], "insurance"),
    (["accounting", "bookkeeping", "cpa", "tax"], "accounting"),
    (["law", "attorney", "legal"], "law firm"),
    (["real estate", "realty", "realtor"], "real estate"),
    (["marketing", "digital", "seo", "advertising"], "digital marketing"),
    (["dental", "dentist"], "dentist"),
    (["medical", "clinic", "healthcare", "health care"], "healthcare"),
    (["auto repair", "mechanic", "automotive"], "auto repair"),
    (["trucking", "logistics", "freight", "transport"], "trucking"),
    (["restaurant", "food", "cafe", "catering"], "restaurant"),
    (["staffing", "recruiting", "employment"], "staffing"),
]


def _infer_industry(business_name: str) -> str:
    name_lower = business_name.lower()
    for keywords, industry in NAME_TO_INDUSTRY:
        if any(kw in name_lower for kw in keywords):
            return industry
    return "business services"  # catch-all


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str[:19], fmt[:len(fmt)])
        except ValueError:
            continue
    return None


class TexasSOSScraper(BaseScraper):
    """
    Scrapes new Texas business formations from data.texas.gov.
    Returns consumer-intent leads (lead_type='consumer') — newly formed
    businesses are at peak buying stage.
    """

    def scrape(self, industry: str, city: str, state: str, max_results: int = 200) -> list[ScrapedLead]:
        """Standard BaseScraper interface — ignores industry/city (fetches all new TX filings)."""
        return self.run(days_back=DEFAULT_LOOKBACK_DAYS, max_results=max_results)

    def run(self, days_back: int = DEFAULT_LOOKBACK_DAYS, max_results: int = 500) -> list[ScrapedLead]:
        cutoff = datetime.now() - timedelta(days=days_back)
        cutoff_str = cutoff.strftime("%Y-%m-%dT00:00:00")

        leads = []
        offset = 0
        limit = 250

        print(f"[tx-sos] Fetching TX business filings since {cutoff_str}…")

        with httpx.Client(timeout=30) as client:
            while len(leads) < max_results:
                url = f"https://{TXSOS_DOMAIN}/resource/{TXSOS_RESOURCE}.json"
                params = {
                    "$limit": limit,
                    "$offset": offset,
                    "$order": "inception_date DESC",
                    "$where": f"inception_date >= '{cutoff_str}'",
                }
                try:
                    resp = client.get(url, params=params)
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    print(f"[tx-sos] HTTP error: {e}")
                    break

                rows = resp.json()
                if not rows:
                    break

                for row in rows:
                    business_name = str(row.get("taxpayer_name", "") or "").strip()
                    if not business_name:
                        continue

                    # Skip clearly inactive or dissolved entities
                    status = str(row.get("taxpayer_status", "") or "").lower()
                    if status and "active" not in status:
                        continue

                    formation_date = _parse_date(str(row.get("inception_date", "") or ""))
                    days_old = (datetime.now() - formation_date).days if formation_date else 999

                    city_name = str(row.get("city", "") or "").strip().title() or "Texas"
                    zip_code = str(row.get("zip", "") or "").strip()[:10] or None
                    address = str(row.get("address", "") or "").strip()
                    full_address = f"{address}, {city_name}, TX" if address else None
                    if full_address and zip_code:
                        full_address += f" {zip_code}"

                    taxpayer_number = str(row.get("taxpayer_number", "") or "").strip()
                    dedup_key = f"tx_sos:{taxpayer_number}" if taxpayer_number else None
                    if not dedup_key:
                        dedup_key = f"tx_sos:{re.sub(r'[^a-z0-9]', '', business_name.lower()[:40])}"

                    industry = _infer_industry(business_name)

                    leads.append(ScrapedLead(
                        business_name=business_name,
                        industry=industry,
                        city=city_name,
                        state="TX",
                        phone=None,
                        email=None,
                        website=None,
                        zip_code=zip_code,
                        full_address=full_address,
                        contact_name=None,
                        source_url=dedup_key,
                        source="texas_sos",
                        lead_type="consumer",       # newly formed = peak buying intent
                        years_in_business=days_old, # repurposed: days since incorporation
                    ))

                if len(rows) < limit:
                    break
                offset += limit
                time.sleep(0.4)

        print(f"[tx-sos] Found {len(leads)} new TX business filings")
        return leads[:max_results]


if __name__ == "__main__":
    import os
    import argparse
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from database import SessionLocal
    from dedup import already_exists
    from models import Lead

    # Inline quality score for standalone use
    def _quality(s: ScrapedLead) -> int:
        score = 0
        if s.phone: score += 25
        if s.email: score += 20
        if s.website: score += 15
        if s.full_address: score += 10
        if s.contact_name: score += 5
        days = s.years_in_business or 999
        if days <= 7: score += 15
        elif days <= 30: score += 10
        elif days <= 60: score += 5
        return min(100, score)

    parser = argparse.ArgumentParser(description="Scrape new Texas SOS business filings")
    parser.add_argument("--days", type=int, default=DEFAULT_LOOKBACK_DAYS, help="Days back to look")
    parser.add_argument("--max", type=int, default=500, help="Max leads to fetch")
    parser.add_argument("--dry-run", action="store_true", help="Print leads without saving")
    args = parser.parse_args()

    scraper = TexasSOSScraper()
    leads = scraper.run(days_back=args.days, max_results=args.max)

    if args.dry_run:
        for lead in leads[:20]:
            print(f"  {lead.business_name} | {lead.industry} | {lead.city} | days_old={lead.years_in_business}")
        print(f"  … ({len(leads)} total)")
        sys.exit(0)

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
        print(f"[tx-sos] Saved {saved} new leads to database")
    except Exception as e:
        session.rollback()
        print(f"[tx-sos] DB error: {e}")
    finally:
        session.close()
