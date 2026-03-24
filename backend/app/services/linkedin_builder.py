"""
LinkedIn URL builder.

Constructs LinkedIn company and people search URLs for every business lead.
No scraping, no API, no rate limits — just string construction.

The generated URLs appear as clickable links in downloaded CSVs so buyers
can jump straight to the LinkedIn profile search for each lead.

Two URLs:
  linkedin_url        — company page search
  linkedin_person_url — people search (only when contact_name is known)
"""
import logging
import urllib.parse
from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000  # pure string ops — very fast


def _company_url(business_name: str, city: str, state: str) -> str:
    q = urllib.parse.quote_plus(f"{business_name} {city} {state}")
    return f"https://www.linkedin.com/search/results/companies/?keywords={q}"


def _person_url(contact_name: str, business_name: str) -> str:
    q = urllib.parse.quote_plus(f"{contact_name} {business_name}")
    return f"https://www.linkedin.com/search/results/people/?keywords={q}"


async def build_linkedin_batch(db: AsyncSession, batch_size: int = BATCH_SIZE) -> int:
    """
    Populate linkedin_url for all business leads that don't have one yet.
    Returns count updated.
    """
    stmt = (
        select(Lead)
        .where(
            and_(
                Lead.linkedin_url.is_(None),
                Lead.lead_type == "business",
            )
        )
        .limit(batch_size)
    )
    result = await db.execute(stmt)
    leads = result.scalars().all()
    if not leads:
        return 0

    for lead in leads:
        lead.linkedin_url = _company_url(lead.business_name, lead.city, lead.state)

    await db.commit()
    logger.info(f"[linkedin_builder] Built LinkedIn URLs for {len(leads)} leads")
    return len(leads)
