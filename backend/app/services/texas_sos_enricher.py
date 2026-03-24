"""
Texas Secretary of State / Comptroller contact enricher.

Searches the Texas Comptroller's Taxable Entity database for the registered
agent or officer name for Texas business leads that have no contact name yet.

Data source: https://mycpa.cpa.state.tx.us/coa/index.do
Free, no API key required.

Runs conservatively (small batches, low concurrency) to be a polite API citizen.
"""
import asyncio
import logging
import re
import urllib.parse
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead

logger = logging.getLogger(__name__)

BATCH_SIZE = 20
CONCURRENCY = 3
COA_BASE = "https://mycpa.cpa.state.tx.us/coa/index.do"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Referer": COA_BASE,
}

# Name must look like "Firstname Lastname [Middle?]"
_NAME_RE = re.compile(r"^[A-Z][a-z]+(?: [A-Z]\.?)? [A-Z][a-z]+$")


async def _lookup(business_name: str, client: httpx.AsyncClient) -> tuple[str | None, str | None]:
    """Return (name, title) from TX Comptroller search, or (None, None)."""
    try:
        params = {"name": business_name, "search": "Search"}
        resp = await client.get(COA_BASE, params=params, timeout=15, headers=HEADERS)
        if resp.status_code != 200:
            return None, None

        soup = BeautifulSoup(resp.text, "lxml")
        rows = soup.select("table tr")

        for row in rows[1:3]:  # check first 2 results
            cells = row.select("td")
            if len(cells) < 2:
                continue
            entity_name = cells[0].get_text(strip=True)
            # Must share at least one significant word with the query
            query_words = {w.lower() for w in business_name.split() if len(w) > 2}
            entity_words = {w.lower() for w in entity_name.split()}
            if not query_words & entity_words:
                continue

            # Follow detail link if present
            link = cells[0].select_one("a[href]")
            if not link:
                continue
            detail_url = urllib.parse.urljoin(COA_BASE, link["href"])
            detail = await client.get(detail_url, timeout=15, headers=HEADERS)
            if detail.status_code != 200:
                continue

            dsoup = BeautifulSoup(detail.text, "lxml")
            # Look for label → value pairs containing agent/officer info
            for label_el in dsoup.select("th, td, dt, label, strong, b"):
                label = label_el.get_text(strip=True).lower()
                if not any(kw in label for kw in ("registered agent", "officer", "director", "owner", "principal")):
                    continue
                # Value is in the next sibling element
                value_el = label_el.find_next_sibling()
                if not value_el:
                    parent = label_el.parent
                    value_el = parent.find_next_sibling() if parent else None
                if not value_el:
                    continue
                value = value_el.get_text(strip=True)
                if _NAME_RE.match(value) and len(value) < 60:
                    title = "Registered Agent" if "registered agent" in label else "Officer"
                    return value, title

    except Exception as e:
        logger.debug(f"[texas_sos] Error for {business_name!r}: {e}")
    return None, None


async def enrich_texas_contacts_batch(db: AsyncSession, batch_size: int = BATCH_SIZE) -> int:
    """
    Enrich Texas business leads with registered agent/officer names from
    the TX Comptroller. Returns count of leads enriched.
    """
    stmt = (
        select(Lead)
        .where(
            and_(
                Lead.state == "TX",
                Lead.lead_type == "business",
                Lead.contact_name.is_(None),
                Lead.texas_sos_attempted_at.is_(None),
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
        lead.texas_sos_attempted_at = now
    await db.flush()

    semaphore = asyncio.Semaphore(CONCURRENCY)
    found_count = 0

    async with httpx.AsyncClient(follow_redirects=True) as client:

        async def _process(lead: Lead) -> bool:
            async with semaphore:
                try:
                    name, title = await _lookup(lead.business_name, client)
                    if name:
                        lead.contact_name = name
                        lead.contact_title = title
                        lead.ai_scored_at = None
                        lead.conversion_score = None
                        return True
                except Exception as e:
                    logger.debug(f"[texas_sos] {lead.business_name}: {e}")
                return False

        results = await asyncio.gather(*[_process(lead) for lead in leads])
        found_count = sum(results)

    await db.commit()
    logger.info(f"[texas_sos] {found_count}/{len(leads)} contacts enriched")
    return found_count
