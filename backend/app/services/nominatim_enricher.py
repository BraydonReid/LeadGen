"""
OpenStreetMap Nominatim address enrichment.

For business leads without a street address, searches Nominatim (OpenStreetMap's
free geocoding API) using business name + city + state. Extracts a verified
street address when a confident match is found.

No API key required. Completely free.
Rate limit: 1 request/second per OSM usage policy — concurrency is capped at 1
with a 1-second sleep between requests.
"""
import asyncio
import logging
import re
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead

logger = logging.getLogger(__name__)

BATCH_SIZE = 50
# Nominatim policy: max 1 req/sec — must stay sequential
CONCURRENCY = 1

HEADERS = {
    "User-Agent": "TakeYourLeadToday/1.0 (lead enrichment; contact@takeyourleadtoday.com)",
    "Accept-Language": "en-US,en;q=0.9",
}

# Only accept result types that represent actual businesses / POIs
ACCEPTED_CLASSES = {"amenity", "shop", "office", "craft", "tourism", "leisure", "healthcare"}


def _nominatim_address(business_name: str, city: str, state: str) -> str | None:
    """
    Query Nominatim for a business by name + city + state.
    Returns a formatted street address string or None if no confident match.
    """
    query = f"{business_name}, {city}, {state}, USA"
    try:
        with httpx.Client(timeout=10, headers=HEADERS) as client:
            resp = client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": query,
                    "format": "json",
                    "addressdetails": "1",
                    "limit": "3",
                    "countrycodes": "us",
                },
            )
        if resp.status_code != 200:
            return None

        results = resp.json()
        for r in results:
            # Only accept business/POI result types
            osm_class = r.get("class", "")
            if osm_class not in ACCEPTED_CLASSES:
                continue

            addr = r.get("address", {})
            house = addr.get("house_number", "").strip()
            road = addr.get("road", "").strip()
            result_city = (
                addr.get("city")
                or addr.get("town")
                or addr.get("village")
                or addr.get("county")
                or ""
            ).strip()
            result_state = addr.get("state", "").strip()
            postcode = addr.get("postcode", "").strip()

            # Must have a street number + road
            if not house or not road:
                continue

            # City must loosely match (case-insensitive, allow partial)
            if city.lower() not in result_city.lower() and result_city.lower() not in city.lower():
                continue

            # State must match (full name or abbreviation)
            if state.upper() not in result_state.upper() and result_state.upper() not in state.upper():
                continue

            street = f"{house} {road}"
            parts = [street, result_city or city, state.upper()]
            if postcode:
                parts.append(postcode)
            return ", ".join(parts)

    except Exception:
        pass
    return None


async def nominatim_enrich_batch(db: AsyncSession, batch_size: int = BATCH_SIZE) -> int:
    """
    Run Nominatim address lookup for business leads without a street address.
    Returns count of addresses found.
    """
    stmt = (
        select(Lead)
        .where(
            and_(
                Lead.full_address.is_(None),
                Lead.nominatim_attempted_at.is_(None),
                Lead.lead_type == "business",
                Lead.city.isnot(None),
                Lead.state.isnot(None),
            )
        )
        .order_by(Lead.conversion_score.desc().nulls_last())
        .limit(batch_size)
    )
    result = await db.execute(stmt)
    leads = result.scalars().all()
    if not leads:
        return 0

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for lead in leads:
        lead.nominatim_attempted_at = now
    await db.flush()

    semaphore = asyncio.Semaphore(CONCURRENCY)
    found_count = 0

    async def _process(lead: Lead) -> bool:
        async with semaphore:
            try:
                address = await asyncio.to_thread(
                    _nominatim_address,
                    lead.business_name,
                    lead.city,
                    lead.state,
                )
                # 1 req/sec rate limit — sleep after every request
                await asyncio.sleep(1.1)
                if address:
                    lead.full_address = address
                    lead.ai_scored_at = None
                    lead.conversion_score = None
                    return True
            except Exception as e:
                logger.debug(f"[nominatim] {lead.business_name} {lead.city}: {e}")
            return False

    results = await asyncio.gather(*[_process(lead) for lead in leads])
    found_count = sum(results)

    await db.commit()
    logger.info(f"[nominatim] {found_count}/{len(leads)} addresses found")
    return found_count
