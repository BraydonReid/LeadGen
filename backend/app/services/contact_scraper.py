"""
Website About/Team page contact scraper.

Visits lead websites looking for About, Team, and Staff pages to extract:
  - Contact/owner name
  - Job title (Owner, President, CEO, Founder, etc.)

Uses the same website infrastructure as the email scraper but focuses
on structured data and text patterns that identify decision-makers.

No API key required. 100% free.
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead

logger = logging.getLogger(__name__)

CONCURRENCY = 15

ABOUT_PATHS = [
    "/about", "/about-us", "/our-team", "/team", "/staff",
    "/meet-the-team", "/about/team", "/who-we-are", "/company",
    "/meet-us", "/the-team",
]

OWNER_TITLES = {
    "owner", "founder", "co-founder", "president", "ceo",
    "chief executive", "principal", "managing director",
    "general manager", "director", "proprietor",
    "partner", "managing partner", "managing member", "operator",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}


async def _fetch(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url, timeout=10, follow_redirects=True, headers=HEADERS)
        if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
            return resp.text
    except Exception:
        pass
    return None


def _extract_contact(html: str) -> tuple[str | None, str | None]:
    """Return (name, title) from page HTML, or (None, None)."""
    soup = BeautifulSoup(html, "lxml")

    # 1. JSON-LD — most reliable when present
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.get_text())
            items = data if isinstance(data, list) else [data]
            for item in items:
                t = item.get("@type", "")
                if t == "Person":
                    name = item.get("name", "").strip()
                    title = item.get("jobTitle", "").strip() or None
                    if name and len(name.split()) >= 2:
                        return name, title
                if t in ("LocalBusiness", "Organization"):
                    for key in ("founder", "employee", "member"):
                        person = item.get(key)
                        if isinstance(person, dict):
                            name = person.get("name", "").strip()
                            title = person.get("jobTitle", "").strip() or None
                            if name and len(name.split()) >= 2:
                                return name, title
        except Exception:
            pass

    # 2. itemprop="name" near a job-title indicator
    for name_el in soup.select("[itemprop='name']"):
        name = name_el.get_text(strip=True)
        if not name or len(name.split()) < 2 or len(name) > 60:
            continue
        container = name_el.find_parent(["article", "div", "section", "li"])
        if container:
            title_el = container.select_one(
                "[itemprop='jobTitle'], [class*='title'], [class*='position'], [class*='role']"
            )
            if title_el:
                title_text = title_el.get_text(strip=True).lower()
                if any(t in title_text for t in OWNER_TITLES):
                    return name, title_el.get_text(strip=True)

    # 3. Text pattern — "Owner: John Smith" or "John Smith, Owner"
    text = soup.get_text(" ", strip=True)
    for kw in OWNER_TITLES:
        patterns = [
            re.compile(
                r"(?i)" + re.escape(kw) + r"\s*[:\-]\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})"
            ),
            re.compile(
                r"([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})\s*,\s*" + re.escape(kw),
                re.IGNORECASE,
            ),
        ]
        for pat in patterns:
            m = pat.search(text)
            if m:
                name = m.group(1).strip()
                if 5 < len(name) < 60:
                    return name, kw.title()

    return None, None


async def scrape_contact_batch(db: AsyncSession, batch_size: int = 100) -> int:
    """
    Scan websites for owner/contact names and decision-maker titles.
    Only runs on business leads with a confirmed-live website but no contact_name.
    Returns count of contacts found.
    """
    stmt = (
        select(Lead)
        .where(
            and_(
                Lead.website.isnot(None),
                Lead.website_status == "ok",
                Lead.contact_name.is_(None),
                Lead.contact_scrape_attempted_at.is_(None),
                Lead.lead_type == "business",
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

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for lead in leads:
        lead.contact_scrape_attempted_at = now
    await db.flush()

    semaphore = asyncio.Semaphore(CONCURRENCY)
    found_count = 0

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:

        async def _process(lead: Lead) -> bool:
            async with semaphore:
                try:
                    base = lead.website if lead.website.startswith("http") else f"https://{lead.website}"
                    # Try homepage first
                    html = await _fetch(client, base)
                    name, title = _extract_contact(html) if html else (None, None)

                    # Try About/Team sub-pages
                    if not name:
                        for path in ABOUT_PATHS:
                            html = await _fetch(client, urljoin(base, path))
                            if html:
                                name, title = _extract_contact(html)
                                if name:
                                    break

                    if name:
                        lead.contact_name = name
                        lead.contact_title = title
                        # Reset AI score so it gets re-scored with the richer contact data
                        lead.ai_scored_at = None
                        lead.conversion_score = None
                        return True
                except Exception as e:
                    logger.debug(f"[contact_scraper] {lead.website}: {e}")
                return False

        results = await asyncio.gather(*[_process(lead) for lead in leads])
        found_count = sum(results)

    await db.commit()
    logger.info(f"[contact_scraper] {found_count}/{len(leads)} contacts found")
    return found_count
