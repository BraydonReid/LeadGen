"""
Website email scraper — finds contact emails directly from lead websites.

Strategy:
  1. Fetch the homepage, look for mailto: links and email patterns
  2. If nothing found, try /contact, /contact-us, /about, /about-us
  3. Filter junk (noreply, wordpress, example.com, image filenames, etc.)
  4. Prefer emails at the lead's own domain (most likely real contact)
  5. Store best result; mark attempted either way

Runs concurrently — up to CONCURRENCY leads processed simultaneously.

Expected hit rate: 40-55% of leads with websites.
No API key required. No monthly limits. 100% free.
"""
import asyncio
import logging
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead

logger = logging.getLogger(__name__)

# How many websites to fetch simultaneously
CONCURRENCY = 20

# Pages to check beyond homepage (tried in order if homepage yields nothing)
CONTACT_PATHS = ["/contact", "/contact-us", "/about", "/about-us", "/team", "/reach-us"]

# Reject emails matching these patterns — they're system addresses, not contacts
JUNK_PATTERNS = re.compile(
    r"(noreply|no-reply|donotreply|do-not-reply|wordpress|"
    r"admin@wordpress|example\.com|example\.org|sentry|"
    r"woocommerce|mailchimp|constantcontact|hubspot|"
    r"@\d+x\.|\.png@|\.jpg@|\.gif@|unsubscribe|"
    r"privacy@|legal@|dmca@|abuse@|postmaster@)",
    re.IGNORECASE,
)

# General email regex
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _score_email(email: str, own_domain: str) -> int:
    """Higher = better. Used to pick the best email when multiple found."""
    email_lower = email.lower()
    score = 0
    if own_domain and email_lower.endswith(f"@{own_domain}"):
        score += 100
    local = email_lower.split("@")[0]
    if re.match(r"^[a-z]+\.[a-z]+$", local):
        score += 30
    if local in ("info", "contact", "hello", "hi", "sales", "support"):
        score += 10
    if local in ("admin", "webmaster", "mail", "email"):
        score -= 10
    return score


def _pick_best(emails: list[str], own_domain: str) -> str | None:
    valid = [e for e in emails if not JUNK_PATTERNS.search(e)]
    if not valid:
        return None
    return max(valid, key=lambda e: _score_email(e, own_domain))


async def _fetch_html(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url, timeout=10, follow_redirects=True, headers=HEADERS)
        if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
            return resp.text
    except Exception:
        pass
    return None


def _emails_from_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    found: set[str] = set()

    # 1. mailto: links — most reliable
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if href.lower().startswith("mailto:"):
            email = href[7:].split("?")[0].strip()
            if EMAIL_RE.match(email):
                found.add(email.lower())

    # 2. JSON-LD structured data (schema.org)
    for script in soup.find_all("script", type="application/ld+json"):
        found.update(m.lower() for m in EMAIL_RE.findall(script.get_text()))

    # 3. Meta tags
    for meta in soup.find_all("meta"):
        content = meta.get("content", "")
        if EMAIL_RE.match(content.strip()):
            found.add(content.strip().lower())

    # 4. Plain text scan — last resort
    for m in EMAIL_RE.findall(soup.get_text(" ", strip=True)):
        found.add(m.lower())

    return list(found)


async def scrape_email_for_lead(website: str, client: httpx.AsyncClient) -> str | None:
    """Attempt to find a contact email for a single website. Reuses shared client."""
    own_domain = _extract_domain(website)
    base_url = website if website.startswith("http") else f"https://{website}"

    html = await _fetch_html(client, base_url)
    if html:
        best = _pick_best(_emails_from_html(html), own_domain)
        if best:
            return best

    for path in CONTACT_PATHS:
        html = await _fetch_html(client, urljoin(base_url, path))
        if html:
            best = _pick_best(_emails_from_html(html), own_domain)
            if best:
                return best

    return None


async def scrape_email_batch(db: AsyncSession, batch_size: int = 100) -> int:
    """
    Scrape emails from lead websites concurrently.
    Processes up to CONCURRENCY=10 leads simultaneously.
    Prioritizes AI-scored leads (highest conversion value first).
    Returns count of emails found.
    """
    stmt = (
        select(Lead)
        .where(
            and_(
                Lead.website.isnot(None),
                Lead.email.is_(None),
                Lead.website_scrape_attempted_at.is_(None),
            )
        )
        .order_by(
            Lead.conversion_score.desc().nulls_last(),
            Lead.quality_score.desc().nulls_last(),
        )
        .limit(batch_size)
    )
    result = await db.execute(stmt)
    leads = result.scalars().all()

    if not leads:
        return 0

    now = datetime.utcnow()
    # Mark all as attempted up front so a crash doesn't leave them un-attempted
    for lead in leads:
        lead.website_scrape_attempted_at = now
    await db.flush()

    semaphore = asyncio.Semaphore(CONCURRENCY)
    found_count = 0

    async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers=HEADERS) as client:

        async def _process(lead: Lead) -> bool:
            async with semaphore:
                try:
                    base_url = lead.website if lead.website.startswith("http") else f"https://{lead.website}"
                    # Check website liveness first (used for dead-site detection)
                    try:
                        head = await client.head(base_url, timeout=8, follow_redirects=True)
                        if head.status_code >= 400:
                            lead.website_status = "dead"
                        else:
                            lead.website_status = "ok"
                    except Exception:
                        lead.website_status = "dead"

                    if lead.website_status == "ok":
                        email = await scrape_email_for_lead(lead.website, client)
                        if email:
                            lead.email = email
                            lead.email_source = "website"
                            lead.email_found_at = now
                            lead.ai_scored_at = None
                            lead.conversion_score = None
                            return True
                except Exception as e:
                    logger.debug(f"[website_scraper] Error on {lead.website}: {e}")
                return False

        results = await asyncio.gather(*[_process(lead) for lead in leads])
        found_count = sum(results)

    await db.commit()

    hit_rate = round(found_count / len(leads) * 100) if leads else 0
    logger.info(
        f"[website_scraper] Batch done — {found_count}/{len(leads)} emails found "
        f"({hit_rate}% hit rate)"
    )
    return found_count
