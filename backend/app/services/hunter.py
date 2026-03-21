"""
Hunter.io API client.

Finds email addresses for businesses given their website domain.
Uses the Domain Search endpoint — returns all emails found for a domain,
ranked by confidence score.

Requires HUNTER_API_KEY in .env (free tier: 25 searches/month).
"""
import logging
from urllib.parse import urlparse

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

HUNTER_DOMAIN_SEARCH = "https://api.hunter.io/v2/domain-search"
HUNTER_EMAIL_FINDER = "https://api.hunter.io/v2/email-finder"

# Only accept emails above this confidence threshold
MIN_CONFIDENCE = 70


def _extract_domain(website_url: str) -> str | None:
    """Strip protocol/path from a URL to get just the domain."""
    try:
        url = website_url if "://" in website_url else f"https://{website_url}"
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        # Remove www. prefix
        domain = domain.lstrip("www.")
        return domain.split("/")[0] if domain else None
    except Exception:
        return None


async def find_email_for_domain(domain: str) -> str | None:
    """
    Search Hunter.io for any email address at the given domain.
    Returns the highest-confidence email, or None if not found.
    """
    if not settings.hunter_api_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                HUNTER_DOMAIN_SEARCH,
                params={"domain": domain, "api_key": settings.hunter_api_key, "limit": 5},
            )
            if resp.status_code == 429:
                logger.warning("[hunter] Rate limited")
                return None
            if resp.status_code != 200:
                return None

            data = resp.json().get("data", {})
            emails = data.get("emails", [])
            if not emails:
                return None

            # Return highest-confidence email that meets threshold
            best = max(emails, key=lambda e: e.get("confidence", 0))
            if best.get("confidence", 0) >= MIN_CONFIDENCE:
                return best.get("value")
    except Exception as e:
        logger.debug(f"[hunter] domain search error for {domain}: {e}")
    return None


async def find_email_for_lead(website: str) -> str | None:
    """
    Given a lead's website URL, extract the domain and search Hunter.io.
    Returns a verified email or None.
    """
    domain = _extract_domain(website)
    if not domain:
        return None
    return await find_email_for_domain(domain)
