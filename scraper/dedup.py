import re
from datetime import datetime, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from models import Lead


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def fingerprint(business_name: str, phone: str | None, website: str | None) -> str:
    return normalize(business_name) + "|" + normalize(phone or website or "")


def already_exists(
    session: Session,
    source_url: str | None,
    business_name: str,
    phone: str | None,
    website: str | None,
    state: str,
) -> bool:
    """
    Return True if this lead is already in the database.
    If found, refreshes the lead's scraped_date so active businesses
    don't age out of the freshness window.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Primary dedup: source_url (exact match per listing page) — uses unique index, O(1)
    if source_url:
        existing = session.query(Lead).filter(Lead.source_url == source_url).first()
        if existing:
            existing.scraped_date = now
            session.flush()
            return True

    # Fallback dedup: targeted DB query on name + contact info rather than loading all state leads
    # Build a short prefix from the normalized name for the LIKE query (DB-side filter)
    normalized_name = normalize(business_name)
    name_prefix = normalized_name[:30] if normalized_name else ""

    # Build contact filter: match leads that share phone OR website
    contact_filters = []
    if phone:
        contact_filters.append(Lead.phone == phone)
    if website:
        # Strip protocol for comparison
        domain = re.sub(r"^https?://", "", website.lower().strip()).rstrip("/")
        contact_filters.append(func.lower(Lead.website).like(f"%{domain}%"))

    # If we have no contact info at all, fall back to name-only match within state
    if contact_filters:
        candidates = (
            session.query(Lead)
            .filter(
                Lead.state == state.upper(),
                or_(*contact_filters),
            )
            .limit(20)
            .all()
        )
    else:
        # Name-prefix match only — limited to 20 candidates to avoid full scan
        candidates = (
            session.query(Lead)
            .filter(
                Lead.state == state.upper(),
                func.lower(Lead.business_name).like(f"{name_prefix[:20]}%"),
            )
            .limit(20)
            .all()
        )

    fp = fingerprint(business_name, phone, website)
    for lead in candidates:
        if fingerprint(lead.business_name, lead.phone, lead.website) == fp:
            lead.scraped_date = now
            session.flush()
            return True

    return False
