"""
NPI Registry enrichment for healthcare leads.

The National Provider Identifier (NPI) Registry is a completely free,
unlimited government API (cms.hhs.gov) that returns verified:
  - Practitioner legal name + credential (Dr., MD, DDS, etc.)
  - Primary practice address
  - Provider taxonomy / specialty

Targets: dentist, dental, orthodontist, chiropractor, physical therapy,
         optometrist, podiatrist, dermatologist, urgent care, doctor,
         physician, medical, healthcare, clinic

No API key required. No rate limits documented.
"""
import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead

logger = logging.getLogger(__name__)

BATCH_SIZE = 200
CONCURRENCY = 10

NPI_API = "https://npiregistry.cms.hhs.gov/api/"

# Industries where NPI lookup is worthwhile
HEALTHCARE_KEYWORDS = {
    "dentist", "dental", "orthodont", "chiropract", "physical therapy",
    "optometr", "podiatr", "dermatolog", "urgent care", "physician",
    "medical", "healthcare", "clinic", "doctor", "orthopedic", "cardiolog",
    "pediatric", "neurol", "psychiatr", "psycholog", "therapist",
}


def _is_healthcare(industry: str) -> bool:
    low = industry.lower()
    return any(kw in low for kw in HEALTHCARE_KEYWORDS)


def _credential_to_title(credential: str | None) -> str | None:
    """Map NPI credential code to a readable title."""
    if not credential:
        return None
    cred = credential.upper().strip("., ")
    mapping = {
        "MD": "MD", "DO": "DO", "DDS": "DDS", "DMD": "DMD",
        "DPM": "DPM", "OD": "OD", "DC": "DC", "PT": "PT",
        "NP": "NP", "PA": "PA", "RN": "RN", "PHD": "PhD",
        "PSYD": "PsyD", "AUD": "AUD",
    }
    return mapping.get(cred, credential.strip())


def _name_similarity(a: str, b: str) -> float:
    """Rough token-overlap similarity between two business names."""
    ta = set(a.lower().split())
    tb = set(b.lower().split())
    # Remove generic words
    stop = {"the", "a", "of", "and", "inc", "llc", "corp", "ltd", "co"}
    ta -= stop
    tb -= stop
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def _query_npi_org(business_name: str, city: str, state: str) -> dict | None:
    """Search NPI registry for an organization by name + city + state."""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(NPI_API, params={
                "version": "2.1",
                "enumeration_type": "NPI-2",  # Organizations
                "organization_name": business_name[:60],
                "city": city,
                "state": state,
                "limit": "5",
            })
        if resp.status_code != 200:
            return None
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return None
        # Pick the result with the best name similarity
        best = max(results, key=lambda r: _name_similarity(
            r.get("basic", {}).get("organization_name", ""), business_name
        ))
        sim = _name_similarity(
            best.get("basic", {}).get("organization_name", ""), business_name
        )
        return best if sim >= 0.4 else None
    except Exception:
        return None


def _query_npi_individual(contact_name: str, city: str, state: str, taxonomy: str = "") -> dict | None:
    """Search NPI registry for an individual provider by name + city + state."""
    parts = contact_name.strip().split()
    if len(parts) < 2:
        return None
    first, last = parts[0], parts[-1]
    try:
        with httpx.Client(timeout=10) as client:
            params = {
                "version": "2.1",
                "enumeration_type": "NPI-1",  # Individuals
                "first_name": first,
                "last_name": last,
                "city": city,
                "state": state,
                "limit": "3",
            }
            resp = client.get(NPI_API, params=params)
        if resp.status_code != 200:
            return None
        results = resp.json().get("results", [])
        return results[0] if results else None
    except Exception:
        return None


def _extract_from_result(result: dict) -> dict:
    """Extract contact_name, contact_title, full_address, zip_code, npi_number from an NPI result."""
    out: dict = {}
    basic = result.get("basic", {})

    # NPI number
    out["npi_number"] = result.get("number", "")

    # Name — individual providers have first_name/last_name, orgs have organization_name
    enum_type = result.get("enumeration_type", "")
    if enum_type == "NPI-1":
        first = basic.get("first_name", "").strip().title()
        last = basic.get("last_name", "").strip().title()
        if first and last:
            out["contact_name"] = f"{first} {last}"
        credential = basic.get("credential", "")
        out["contact_title"] = _credential_to_title(credential)
    else:
        # Organization — extract authorized official as contact if available
        official = basic.get("authorized_official_first_name", "")
        if official:
            o_first = official.strip().title()
            o_last = basic.get("authorized_official_last_name", "").strip().title()
            if o_first and o_last:
                out["contact_name"] = f"{o_first} {o_last}"
            credential = basic.get("authorized_official_credential", "")
            out["contact_title"] = _credential_to_title(credential) or basic.get("authorized_official_title_or_position", "")

    # Address — prefer practice location (address_purpose = "LOCATION")
    addresses = result.get("addresses", [])
    addr = next(
        (a for a in addresses if a.get("address_purpose") == "LOCATION"),
        addresses[0] if addresses else {}
    )
    if addr:
        street = addr.get("address_1", "").strip().title()
        city_r = addr.get("city", "").strip().title()
        state_r = addr.get("state", "").strip().upper()
        postal = addr.get("postal_code", "")[:5]
        if street and city_r and state_r:
            parts = [street, city_r, state_r]
            if postal:
                parts.append(postal)
            out["full_address"] = ", ".join(parts)
            out["zip_code"] = postal or None

    return out


async def npi_enrich_batch(db: AsyncSession, batch_size: int = BATCH_SIZE) -> int:
    """
    Run NPI Registry lookup for healthcare business leads.
    Enriches: contact_name, contact_title, full_address, zip_code, npi_number.
    Returns count of leads enriched with at least one new field.
    """
    stmt = (
        select(Lead)
        .where(
            and_(
                Lead.npi_attempted_at.is_(None),
                Lead.lead_type == "business",
                Lead.city.isnot(None),
                Lead.state.isnot(None),
            )
        )
        .order_by(Lead.conversion_score.desc().nulls_last())
        .limit(batch_size * 3)  # Over-fetch to account for non-healthcare filtering
    )
    result = await db.execute(stmt)
    all_leads = result.scalars().all()

    # Filter to healthcare industries in Python (cheaper than DB ILIKE)
    leads = [l for l in all_leads if _is_healthcare(l.industry)][:batch_size]
    if not leads:
        # Mark the non-healthcare ones as attempted so they don't get re-fetched
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for l in all_leads:
            l.npi_attempted_at = now
        await db.commit()
        return 0

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for lead in leads:
        lead.npi_attempted_at = now
    await db.flush()

    semaphore = asyncio.Semaphore(CONCURRENCY)
    found_count = 0

    async def _process(lead: Lead) -> bool:
        async with semaphore:
            try:
                # Try org lookup first, fall back to individual if contact_name is known
                npi_result = await asyncio.to_thread(
                    _query_npi_org, lead.business_name, lead.city, lead.state
                )
                if not npi_result and lead.contact_name:
                    npi_result = await asyncio.to_thread(
                        _query_npi_individual, lead.contact_name, lead.city, lead.state
                    )

                if not npi_result:
                    return False

                fields = _extract_from_result(npi_result)
                enriched = False

                if fields.get("npi_number"):
                    lead.npi_number = fields["npi_number"]
                    enriched = True
                if fields.get("contact_name") and not lead.contact_name:
                    lead.contact_name = fields["contact_name"]
                    enriched = True
                if fields.get("contact_title") and not lead.contact_title:
                    lead.contact_title = fields["contact_title"]
                    enriched = True
                if fields.get("full_address") and not lead.full_address:
                    lead.full_address = fields["full_address"]
                    enriched = True
                if fields.get("zip_code") and not lead.zip_code:
                    lead.zip_code = fields["zip_code"]
                    enriched = True

                if enriched:
                    lead.ai_scored_at = None
                    lead.conversion_score = None
                    return True

            except Exception as e:
                logger.debug(f"[npi] {lead.business_name} {lead.city}: {e}")
            return False

    results = await asyncio.gather(*[_process(lead) for lead in leads])
    found_count = sum(results)

    await db.commit()
    logger.info(f"[npi] {found_count}/{len(leads)} healthcare leads enriched")
    return found_count
