"""
Social media link extractor.

Visits lead websites and extracts Facebook page URL and Instagram handle
from footer/header links. Runs as a separate pass so all existing leads
can be enriched retroactively.

No API key required. Completely free.
"""
import asyncio
import logging
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead

logger = logging.getLogger(__name__)

CONCURRENCY = 20
BATCH_SIZE = 200

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}

# Noise patterns to ignore in social links
_FB_SKIP = {"facebook.com/sharer", "facebook.com/share?", "facebook.com/dialog",
             "facebook.com/plugins", "facebook.com/tr?", "facebook.com/v"}
_IG_SKIP = {"instagram.com/p/", "instagram.com/reel/", "instagram.com/tv/"}


def _clean_facebook_url(href: str) -> str | None:
    """Validate and normalise a Facebook href. Returns None if it looks like a widget/tracker."""
    h = href.lower()
    if not ("facebook.com/" in h or "fb.com/" in h):
        return None
    if any(s in h for s in _FB_SKIP):
        return None
    # Strip query strings for cleanliness
    url = href.split("?")[0].rstrip("/")
    # Must have a path segment after the domain
    after_domain = url.split("facebook.com/")[-1].split("fb.com/")[-1]
    if len(after_domain) < 2:
        return None
    return url


def _clean_instagram_url(href: str) -> str | None:
    """Validate an Instagram href."""
    h = href.lower()
    if "instagram.com/" not in h:
        return None
    if any(s in h for s in _IG_SKIP):
        return None
    url = href.split("?")[0].rstrip("/")
    after_domain = url.split("instagram.com/")[-1]
    if len(after_domain) < 2:
        return None
    return url


def _extract_social(html: str) -> tuple[str | None, str | None]:
    """Return (facebook_url, instagram_url) from page HTML."""
    soup = BeautifulSoup(html, "lxml")
    fb_url: str | None = None
    ig_url: str | None = None

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not fb_url:
            fb_url = _clean_facebook_url(href)
        if not ig_url:
            ig_url = _clean_instagram_url(href)
        if fb_url and ig_url:
            break

    return fb_url, ig_url


async def scrape_social_batch(db: AsyncSession, batch_size: int = BATCH_SIZE) -> int:
    """
    Fetch homepage of leads with a website and extract social media links.
    Returns count of leads where at least one social link was found.
    """
    stmt = (
        select(Lead)
        .where(
            and_(
                Lead.website.isnot(None),
                Lead.social_scrape_attempted_at.is_(None),
                Lead.lead_type == "business",
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
        lead.social_scrape_attempted_at = now
    await db.flush()

    semaphore = asyncio.Semaphore(CONCURRENCY)
    found_count = 0

    async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers=HEADERS) as client:

        async def _process(lead: Lead) -> bool:
            async with semaphore:
                try:
                    base = lead.website if lead.website.startswith("http") else f"https://{lead.website}"
                    resp = await client.get(base, timeout=8)
                    if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""):
                        return False

                    fb, ig = _extract_social(resp.text)
                    if fb or ig:
                        if fb:
                            lead.facebook_url = fb
                        if ig:
                            lead.instagram_url = ig
                        lead.ai_scored_at = None
                        lead.conversion_score = None
                        return True
                except Exception as e:
                    logger.debug(f"[social_scraper] {lead.website}: {e}")
                return False

        results = await asyncio.gather(*[_process(lead) for lead in leads])
        found_count = sum(results)

    await db.commit()
    logger.info(f"[social_scraper] {found_count}/{len(leads)} social links found")
    return found_count
