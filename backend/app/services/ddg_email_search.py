"""
DuckDuckGo email search enrichment.

For leads without emails, searches DuckDuckGo for:
  "[business name]" "[city]" email contact

Extracts emails from search result titles and snippets.
This surfaces emails listed on Yelp, YellowPages, BBB, Facebook,
Superpages, and other directories — all in one free search.

No API key required. No rate limit fees. Completely free.
"""
import asyncio
import logging
import re
from datetime import datetime, timezone

from duckduckgo_search import DDGS
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead

logger = logging.getLogger(__name__)

BATCH_SIZE = 30
CONCURRENCY = 3  # DDG is aggressive about rate limiting concurrent requests

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE)

JUNK_PATTERNS = re.compile(
    r"(noreply|no-reply|donotreply|example\.com|sentry|wordpress|"
    r"woocommerce|mailchimp|constantcontact|privacy@|legal@|"
    r"abuse@|postmaster@|\.png@|\.jpg@)",
    re.IGNORECASE,
)


def _search_email(business_name: str, city: str, state: str, own_domain: str | None) -> str | None:
    """Search DDG and extract the first valid email from results."""
    query = f'"{business_name}" "{city}" {state} email contact'
    try:
        with DDGS() as ddg:
            results = list(ddg.text(query, max_results=5))
        for r in results:
            text = f"{r.get('title', '')} {r.get('body', '')}"
            emails = EMAIL_RE.findall(text)
            for email in emails:
                email_lower = email.lower()
                if JUNK_PATTERNS.search(email_lower):
                    continue
                # Prefer emails at the lead's own domain
                if own_domain and email_lower.endswith(f"@{own_domain}"):
                    return email_lower
                # Accept any business-looking email
                if not email_lower.endswith(("@gmail.com", "@yahoo.com", "@hotmail.com",
                                              "@outlook.com", "@icloud.com", "@aol.com")):
                    return email_lower
    except Exception:
        pass
    return None


async def ddg_email_search_batch(db: AsyncSession, batch_size: int = BATCH_SIZE) -> int:
    """
    Run DuckDuckGo email search for leads without emails.
    Returns count of emails found.
    """
    stmt = (
        select(Lead)
        .where(
            and_(
                Lead.email.is_(None),
                Lead.ddg_search_attempted_at.is_(None),
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
        lead.ddg_search_attempted_at = now
    await db.flush()

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def _process(lead: Lead) -> bool:
        async with semaphore:
            try:
                from urllib.parse import urlparse
                own_domain = None
                if lead.website:
                    try:
                        own_domain = urlparse(lead.website).netloc.lower().replace("www.", "")
                    except Exception:
                        pass

                email = await asyncio.to_thread(
                    _search_email,
                    lead.business_name,
                    lead.city,
                    lead.state,
                    own_domain,
                )
                if email:
                    lead.email = email
                    lead.email_source = "ddg_search"
                    lead.email_found_at = now
                    lead.ai_scored_at = None
                    lead.conversion_score = None
                    return True
            except Exception as e:
                logger.debug(f"[ddg_search] {lead.business_name}: {e}")
            return False

    results = await asyncio.gather(*[_process(lead) for lead in leads])
    found_count = sum(results)

    await db.commit()
    logger.info(f"[ddg_search] {found_count}/{len(leads)} emails found")
    return found_count
