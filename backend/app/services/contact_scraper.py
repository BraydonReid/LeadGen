"""
Website enrichment scraper.

Visits lead websites and extracts everything possible in a single pass:
  - Contact/owner name and title
  - Street address
  - Years in business (from "Founded", "Est.", "Since" patterns)
  - Aggregate rating + review count (from JSON-LD schema.org)

Resets AI score after any enrichment so the lead gets re-scored with richer data.

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
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead

logger = logging.getLogger(__name__)

CONCURRENCY = 15

ABOUT_PATHS = [
    "/about", "/about-us", "/our-team", "/team", "/staff",
    "/meet-the-team", "/about/team", "/who-we-are", "/company",
    "/meet-us", "/the-team", "/contact", "/contact-us",
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

CURRENT_YEAR = datetime.now().year


async def _fetch(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url, timeout=10, follow_redirects=True, headers=HEADERS)
        if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
            return resp.text
    except Exception:
        pass
    return None


def _extract_contact(html: str) -> tuple[str | None, str | None]:
    """Return (name, title) from page HTML."""
    soup = BeautifulSoup(html, "lxml")

    # 1. JSON-LD
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
            re.compile(r"(?i)" + re.escape(kw) + r"\s*[:\-]\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})"),
            re.compile(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})\s*,\s*" + re.escape(kw), re.IGNORECASE),
        ]
        for pat in patterns:
            m = pat.search(text)
            if m:
                name = m.group(1).strip()
                if 5 < len(name) < 60:
                    return name, kw.title()

    return None, None


def _extract_address(html: str) -> str | None:
    """Extract street address from JSON-LD, <address> tag, or microformat."""
    soup = BeautifulSoup(html, "lxml")

    # 1. JSON-LD schema.org address
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.get_text())
            items = data if isinstance(data, list) else [data]
            for item in items:
                addr = item.get("address") or {}
                if isinstance(addr, str) and len(addr) > 5:
                    return addr.strip()
                if isinstance(addr, dict):
                    street = addr.get("streetAddress", "").strip()
                    city = addr.get("addressLocality", "").strip()
                    state = addr.get("addressRegion", "").strip()
                    postal = addr.get("postalCode", "").strip()
                    if street:
                        parts = [p for p in [street, city, state, postal] if p]
                        return ", ".join(parts)
        except Exception:
            pass

    # 2. <address> HTML tag
    addr_tag = soup.find("address")
    if addr_tag:
        text = addr_tag.get_text(" ", strip=True)
        # Filter out obviously non-address content (too short or looks like email/phone only)
        if 10 < len(text) < 200 and re.search(r"\d", text):
            return re.sub(r"\s+", " ", text).strip()

    # 3. itemprop streetAddress
    el = soup.find(attrs={"itemprop": "streetAddress"})
    if el:
        street = el.get_text(strip=True)
        if street and len(street) > 5:
            city_el = soup.find(attrs={"itemprop": "addressLocality"})
            state_el = soup.find(attrs={"itemprop": "addressRegion"})
            parts = [street]
            if city_el:
                parts.append(city_el.get_text(strip=True))
            if state_el:
                parts.append(state_el.get_text(strip=True))
            return ", ".join(parts)

    return None


def _extract_years_in_business(html: str) -> int | None:
    """Extract years in business from founding year patterns."""
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    patterns = [
        r"(?:founded|established|est\.?|since|serving since)\s+(?:in\s+)?(\d{4})",
        r"(?:in business since|family owned since|serving you since)\s+(\d{4})",
        r"©\s*(\d{4})\b",  # copyright year as fallback
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            year = int(m.group(1))
            if 1900 < year <= CURRENT_YEAR:
                return CURRENT_YEAR - year

    return None


def _extract_rating(html: str) -> tuple[float | None, int | None]:
    """Extract (rating, review_count) from JSON-LD aggregateRating."""
    soup = BeautifulSoup(html, "lxml")

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.get_text())
            items = data if isinstance(data, list) else [data]
            for item in items:
                agg = item.get("aggregateRating") or {}
                if isinstance(agg, dict):
                    rating = agg.get("ratingValue") or agg.get("bestRating")
                    count = agg.get("reviewCount") or agg.get("ratingCount")
                    if rating:
                        try:
                            r = float(rating)
                            c = int(count) if count else None
                            if 1.0 <= r <= 5.0:
                                return r, c
                        except (ValueError, TypeError):
                            pass
        except Exception:
            pass

    return None, None


async def scrape_contact_batch(db: AsyncSession, batch_size: int = 100) -> int:
    """
    Scan lead websites for all enrichable data in a single pass.
    Extracts: contact name/title, address, years in business, rating/reviews.
    Returns count of leads enriched with at least one new field.
    """
    stmt = (
        select(Lead)
        .where(
            and_(
                Lead.website.isnot(None),
                Lead.contact_scrape_attempted_at.is_(None),
                Lead.lead_type == "business",
                or_(
                    Lead.contact_name.is_(None),
                    Lead.full_address.is_(None),
                    Lead.years_in_business.is_(None),
                ),
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
                enriched = False
                try:
                    base = lead.website if lead.website.startswith("http") else f"https://{lead.website}"

                    # Fetch homepage
                    html = await _fetch(client, base)
                    pages = [html] if html else []

                    # Fetch about/contact sub-pages
                    for path in ABOUT_PATHS:
                        sub = await _fetch(client, urljoin(base, path))
                        if sub:
                            pages.append(sub)
                            # Stop after 3 pages to avoid too many requests per lead
                            if len(pages) >= 3:
                                break

                    for page_html in pages:
                        if not page_html:
                            continue

                        # Contact name
                        if not lead.contact_name:
                            name, title = _extract_contact(page_html)
                            if name:
                                lead.contact_name = name
                                lead.contact_title = title
                                enriched = True

                        # Address
                        if not lead.full_address:
                            address = _extract_address(page_html)
                            if address:
                                lead.full_address = address
                                enriched = True

                        # Years in business
                        if not lead.years_in_business:
                            years = _extract_years_in_business(page_html)
                            if years and 0 < years < 200:
                                lead.years_in_business = years
                                enriched = True

                        # Rating — only set if not already from Yelp
                        if not lead.yelp_rating:
                            rating, count = _extract_rating(page_html)
                            if rating:
                                lead.yelp_rating = rating
                                if count and not lead.review_count:
                                    lead.review_count = count
                                enriched = True

                    if enriched:
                        lead.ai_scored_at = None
                        lead.conversion_score = None
                        return True

                except Exception as e:
                    logger.debug(f"[contact_scraper] {lead.website}: {e}")
                return False

        results = await asyncio.gather(*[_process(lead) for lead in leads])
        found_count = sum(results)

    await db.commit()
    logger.info(f"[contact_scraper] {found_count}/{len(leads)} leads enriched")
    return found_count
