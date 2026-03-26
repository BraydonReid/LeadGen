"""
Multi-source address enrichment using free OpenStreetMap geocoders.

Pipeline per lead (in order):
  1. Nominatim (OSM official) — best structured data; strict 1 req/sec limit
  2. Photon (Komoot-hosted OSM)  — same OSM data; ~5 req/sec, good fallback

No API keys required. Both are completely free.
"""
import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead

logger = logging.getLogger(__name__)

BATCH_SIZE = 200

# Per-service concurrency caps
_NOM_SEM: asyncio.Semaphore | None = None   # Nominatim — 1 req/sec (created lazily)
_PHO_SEM: asyncio.Semaphore | None = None   # Photon     — ~5 req/sec


def _get_nominatim_sem() -> asyncio.Semaphore:
    global _NOM_SEM
    if _NOM_SEM is None:
        _NOM_SEM = asyncio.Semaphore(1)
    return _NOM_SEM


def _get_photon_sem() -> asyncio.Semaphore:
    global _PHO_SEM
    if _PHO_SEM is None:
        _PHO_SEM = asyncio.Semaphore(3)
    return _PHO_SEM


HEADERS = {
    "User-Agent": "TakeYourLeadToday/1.0 (lead enrichment; contact@takeyourleadtoday.com)",
    "Accept-Language": "en-US,en;q=0.9",
}

# Nominatim OSM classes that represent actual business POIs
ACCEPTED_CLASSES = {"amenity", "shop", "office", "craft", "tourism", "leisure", "healthcare"}

# US state abbreviation → full name (for Photon which returns full names)
_STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}


def _state_matches(state_abbr: str, result_state: str) -> bool:
    """Return True if result_state matches the abbreviation or its full name."""
    abbr = state_abbr.upper()
    rs = result_state.strip()
    if abbr in rs.upper():
        return True
    full = _STATE_NAMES.get(abbr, "")
    if full and full.lower() in rs.lower():
        return True
    return False


def _city_matches(city: str, result_city: str) -> bool:
    c = city.lower()
    r = result_city.lower()
    return c in r or r in c


# ---------------------------------------------------------------------------
# Nominatim
# ---------------------------------------------------------------------------

def _nominatim_address(business_name: str, city: str, state: str) -> str | None:
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

        for r in resp.json():
            if r.get("class", "") not in ACCEPTED_CLASSES:
                continue
            addr = r.get("address", {})
            house = addr.get("house_number", "").strip()
            road = addr.get("road", "").strip()
            result_city = (
                addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county") or ""
            ).strip()
            result_state = addr.get("state", "").strip()
            postcode = addr.get("postcode", "").strip()

            if not house or not road:
                continue
            if not _city_matches(city, result_city):
                continue
            if not _state_matches(state, result_state):
                continue

            parts = [f"{house} {road}", result_city or city, state.upper()]
            if postcode:
                parts.append(postcode)
            return ", ".join(parts)

    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Photon (Komoot) — same OSM data, higher rate limit
# ---------------------------------------------------------------------------

def _photon_address(business_name: str, city: str, state: str) -> str | None:
    query = f"{business_name}, {city}, {state}"
    try:
        with httpx.Client(timeout=10, headers=HEADERS) as client:
            resp = client.get(
                "https://photon.komoot.io/api/",
                params={"q": query, "limit": "5", "lang": "en"},
            )
        if resp.status_code != 200:
            return None

        for feature in resp.json().get("features", []):
            props = feature.get("properties", {})
            # Must be in USA
            if props.get("country_code", "").upper() != "US":
                continue

            house = str(props.get("housenumber", "")).strip()
            road = str(props.get("street", "")).strip()
            result_city = str(props.get("city") or props.get("town") or props.get("village") or "").strip()
            result_state = str(props.get("state", "")).strip()
            postcode = str(props.get("postcode", "")).strip()

            if not house or not road:
                continue
            if not _city_matches(city, result_city):
                continue
            if not _state_matches(state, result_state):
                continue

            parts = [f"{house} {road}", result_city or city, state.upper()]
            if postcode:
                parts.append(postcode)
            return ", ".join(parts)

    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

async def nominatim_enrich_batch(db: AsyncSession, batch_size: int = BATCH_SIZE) -> int:
    """
    Run multi-source address lookup for business leads without a street address.
    Tries Nominatim first, falls back to Photon. Returns count of addresses found.
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

    nom_sem = _get_nominatim_sem()
    pho_sem = _get_photon_sem()

    async def _process(lead: Lead) -> bool:
        address: str | None = None

        # --- Nominatim (serialized, 1 req/sec) ---
        async with nom_sem:
            try:
                address = await asyncio.to_thread(
                    _nominatim_address, lead.business_name, lead.city, lead.state
                )
            except Exception as e:
                logger.debug(f"[nominatim] {lead.business_name}: {e}")
            await asyncio.sleep(1.1)  # OSM policy: max 1 req/sec

        # --- Photon fallback (up to 3 concurrent, 0.2s sleep) ---
        if not address:
            async with pho_sem:
                try:
                    address = await asyncio.to_thread(
                        _photon_address, lead.business_name, lead.city, lead.state
                    )
                except Exception as e:
                    logger.debug(f"[photon] {lead.business_name}: {e}")
                await asyncio.sleep(0.25)

        if address:
            lead.full_address = address
            lead.ai_scored_at = None
            lead.conversion_score = None
            return True
        return False

    results = await asyncio.gather(*[_process(lead) for lead in leads])
    found_count = sum(results)

    await db.commit()
    logger.info(f"[geocoder] {found_count}/{len(leads)} addresses found (batch of {len(leads)})")
    return found_count
