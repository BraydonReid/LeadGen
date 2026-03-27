"""
SMTP-based email pattern discovery.

For leads whose website the email scraper already visited (and found nothing),
generates common email address patterns and verifies each via a silent
SMTP RCPT TO handshake — no email is ever sent, no API key required.

Catch-all detection: if the server accepts a random UUID address, the domain
accepts everything and we skip it to avoid false positives.

Pattern priority:
  1. Name-derived  (john@domain.com, john.smith@domain.com, jsmith@domain.com …)
  2. Generic       (info@, contact@, hello@, office@, sales@)

No API key required. 100% free.
"""
import asyncio
import logging
import random
import smtplib
import string
from datetime import datetime, timezone
from urllib.parse import urlparse

import dns.resolver
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead

logger = logging.getLogger(__name__)

BATCH_SIZE = 50
CONCURRENCY = 5

EHLO_DOMAIN = "takeyourleadtoday.com"
SENDER = f"verify@{EHLO_DOMAIN}"
GENERIC_LOCALS = ["info", "contact", "hello", "office", "sales", "service", "admin"]


def _domain(website: str) -> str | None:
    try:
        netloc = urlparse(website).netloc.lower().replace("www.", "")
        return netloc if "." in netloc else None
    except Exception:
        return None


def _get_mx(domain: str) -> str | None:
    try:
        records = dns.resolver.resolve(domain, "MX", lifetime=5)
        return str(sorted(records, key=lambda r: r.preference)[0].exchange).rstrip(".")
    except Exception:
        return None


def _smtp_rcpt(email: str, mx_host: str) -> bool:
    """Return True if MX server responds 250 to RCPT TO (address exists)."""
    try:
        with smtplib.SMTP(timeout=5) as s:
            s.connect(mx_host, 25)
            s.helo(EHLO_DOMAIN)
            s.mail(SENDER)
            code, _ = s.rcpt(email)
            return code == 250
    except Exception:
        return False


def _is_catchall(mx_host: str, domain: str) -> bool:
    """True if the server accepts any address (catch-all) — skip these."""
    rand = "".join(random.choices(string.ascii_lowercase, k=18))
    return _smtp_rcpt(f"{rand}@{domain}", mx_host)


def _name_patterns(contact_name: str, domain: str) -> list[str]:
    parts = contact_name.strip().split()
    if len(parts) < 2:
        return []
    f, l = parts[0].lower(), parts[-1].lower()
    return [
        f"{f}@{domain}",
        f"{f}.{l}@{domain}",
        f"{f}{l}@{domain}",
        f"{f[0]}{l}@{domain}",
        f"{f[0]}.{l}@{domain}",
    ]


async def _discover(lead: Lead) -> str | None:
    dom = _domain(lead.website)
    if not dom:
        return None

    mx = await asyncio.to_thread(_get_mx, dom)
    if not mx:
        return None

    # Skip catch-all servers
    if await asyncio.to_thread(_is_catchall, mx, dom):
        return None

    candidates: list[str] = []
    if lead.contact_name:
        candidates.extend(_name_patterns(lead.contact_name, dom))
    candidates.extend(f"{loc}@{dom}" for loc in GENERIC_LOCALS)

    # Deduplicate while keeping order
    seen: set[str] = set()
    unique = [c for c in candidates if not (c in seen or seen.add(c))]  # type: ignore[func-returns-value]

    for email in unique:
        if await asyncio.to_thread(_smtp_rcpt, email, mx):
            return email
    return None


async def smtp_discovery_batch(db: AsyncSession, batch_size: int = BATCH_SIZE) -> int:
    """
    Run SMTP email discovery for leads the website scraper already tried.
    Returns count of emails found.
    """
    stmt = (
        select(Lead)
        .where(
            and_(
                Lead.website.isnot(None),
                Lead.email.is_(None),
                Lead.smtp_discovery_attempted_at.is_(None),
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
        lead.smtp_discovery_attempted_at = now
    await db.flush()

    semaphore = asyncio.Semaphore(CONCURRENCY)
    found_count = 0

    async def _process(lead: Lead) -> bool:
        async with semaphore:
            try:
                email = await asyncio.wait_for(_discover(lead), timeout=45)
                if email:
                    lead.email = email
                    lead.email_source = "smtp_discovery"
                    lead.email_verified = True
                    lead.email_found_at = now
                    lead.ai_scored_at = None
                    lead.conversion_score = None
                    return True
            except Exception as e:
                logger.debug(f"[smtp_discovery] {lead.website}: {e}")
            return False

    results = await asyncio.gather(*[_process(lead) for lead in leads])
    found_count = sum(results)

    await db.commit()
    logger.info(f"[smtp_discovery] {found_count}/{len(leads)} emails found")
    return found_count
