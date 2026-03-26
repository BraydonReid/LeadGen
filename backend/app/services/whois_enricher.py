"""
WHOIS email enrichment.

Many small businesses register their domain with their real contact email.
Looks up the WHOIS record for each lead's domain and extracts the registrant
email, filtering out privacy-protection services.

No API key required. Completely free.
"""
import asyncio
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import whois
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
CONCURRENCY = 20

# Privacy protection services return junk emails — skip them
PRIVACY_PATTERNS = re.compile(
    r"(whoisguard|domainsbyproxy|privacyprotect|whoisprivacy|contactprivacy|"
    r"domainprivacy|proxy|redacted|withheld|not disclosed|above\.com|"
    r"perfect privacy|registrar|godaddy\.com|namecheap\.com|tucows\.com|"
    r"networksolutions|enom\.com|name\.com|uniregistry|internet\.bs)",
    re.IGNORECASE,
)


def _get_domain(website: str) -> str | None:
    try:
        netloc = urlparse(website).netloc.lower().replace("www.", "")
        return netloc if "." in netloc else None
    except Exception:
        return None


def _whois_email(domain: str) -> str | None:
    try:
        w = whois.whois(domain)
        emails = w.get("emails") or []
        if isinstance(emails, str):
            emails = [emails]
        for email in (emails or []):
            if email and "@" in email and not PRIVACY_PATTERNS.search(email):
                return email.lower().strip()
    except Exception:
        pass
    return None


async def whois_enrich_batch(db: AsyncSession, batch_size: int = BATCH_SIZE) -> int:
    """
    Run WHOIS email lookup for leads that haven't been attempted yet.
    Returns count of emails found.
    """
    stmt = (
        select(Lead)
        .where(
            and_(
                Lead.website.isnot(None),
                Lead.email.is_(None),
                Lead.whois_attempted_at.is_(None),
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
        lead.whois_attempted_at = now
    await db.flush()

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def _process(lead: Lead) -> bool:
        async with semaphore:
            try:
                domain = _get_domain(lead.website)
                if not domain:
                    return False
                email = await asyncio.to_thread(_whois_email, domain)
                if email:
                    lead.email = email
                    lead.email_source = "whois"
                    lead.email_found_at = now
                    lead.ai_scored_at = None
                    lead.conversion_score = None
                    return True
            except Exception as e:
                logger.debug(f"[whois] {lead.website}: {e}")
            return False

    results = await asyncio.gather(*[_process(lead) for lead in leads])
    found_count = sum(results)

    await db.commit()
    logger.info(f"[whois] {found_count}/{len(leads)} emails found")
    return found_count
