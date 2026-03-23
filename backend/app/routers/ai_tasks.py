"""
Internal AI task endpoints.
These are not exposed to the public — they're used to trigger background jobs
on-demand (e.g., for manual backfilling or testing).
"""
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.database import get_db
from app.models import Lead
from app.services.openai_client import is_available

logger = logging.getLogger(__name__)
router = APIRouter()

YELP_BUDGET_FILE = Path("/app/history/yelp_budget.json")
YELP_MONTHLY_LIMIT = 5000
YELP_DAILY_LIMIT = 160


@router.post("/internal/score-leads")
async def trigger_scoring(
    batch_size: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Trigger AI scoring for unscored leads. Safe to call repeatedly."""
    if not await is_available():
        return {"error": "OPENAI_API_KEY not configured", "scored": 0}

    from app.services.ai_scoring import score_lead_batch
    count = await score_lead_batch(db, batch_size)
    return {"scored": count, "batch_size": batch_size}


@router.post("/internal/enrich-leads")
async def trigger_enrichment(
    batch_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger Hunter.io email enrichment for leads with websites but no email.
    Safe to call repeatedly — skips leads already attempted.
    Re-queues AI scoring automatically for any lead where an email is found.
    """
    from app.config import settings
    if not settings.hunter_api_key:
        return {"error": "HUNTER_API_KEY not configured", "found": 0}

    from app.services.email_enrichment import enrich_leads_batch
    found = await enrich_leads_batch(db, batch_size)

    # Report how many still need enrichment
    from sqlalchemy import and_
    remaining = (await db.execute(
        select(func.count()).select_from(Lead)
        .where(Lead.website.isnot(None))
        .where(Lead.email.is_(None))
        .where(Lead.enrichment_attempted_at.is_(None))
    )).scalar_one()

    return {"found": found, "batch_size": batch_size, "remaining_unattempted": remaining}


@router.post("/internal/scrape-emails")
async def trigger_website_scrape(
    batch_size: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """
    Scrape contact emails directly from lead websites.
    No API key needed. Safe to call repeatedly — skips already-attempted leads.
    """
    from app.services.website_scraper import scrape_email_batch
    found = await scrape_email_batch(db, batch_size)

    remaining = (await db.execute(
        select(func.count()).select_from(Lead)
        .where(Lead.website.isnot(None))
        .where(Lead.email.is_(None))
        .where(Lead.website_scrape_attempted_at.is_(None))
    )).scalar_one()

    return {"found": found, "batch_size": batch_size, "remaining_unattempted": remaining}


@router.post("/internal/clean-phones")
async def trigger_phone_cleaning(
    batch_size: int = Query(default=2000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """
    Normalize and validate phone numbers for leads not yet processed.
    Safe to call repeatedly — skips already-validated leads.
    """
    from app.services.phone_cleaner import clean_phones_batch, clean_phones_remaining
    result = await clean_phones_batch(db, batch_size)
    remaining = await clean_phones_remaining(db)
    return {**result, "remaining": remaining}


@router.post("/internal/dedup-leads")
async def trigger_deduplication(
    batch_size: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """
    Find and mark duplicate leads by phone number and business name+city.
    Safe to call repeatedly. Keeps the most complete record per group.
    """
    from app.services.deduplication import run_dedup_pass
    return await run_dedup_pass(db, batch_size)


@router.get("/internal/status")
async def platform_status(db: AsyncSession = Depends(get_db)):
    """Overall platform health: lead counts, AI scoring progress, Yelp budget."""
    total = (await db.execute(select(func.count()).select_from(Lead))).scalar_one()
    scored = (await db.execute(
        select(func.count()).select_from(Lead).where(Lead.conversion_score.isnot(None))
    )).scalar_one()
    with_rating = (await db.execute(
        select(func.count()).select_from(Lead).where(Lead.yelp_rating.isnot(None))
    )).scalar_one()
    consumer = (await db.execute(
        select(func.count()).select_from(Lead).where(Lead.lead_type == "consumer")
    )).scalar_one()

    # Yelp budget — read from scraper volume
    yelp = {"status": "no data yet"}
    try:
        if YELP_BUDGET_FILE.exists():
            data = json.loads(YELP_BUDGET_FILE.read_text())
            yelp = {
                "month": data.get("month"),
                "monthly_used": data.get("monthly_used", 0),
                "monthly_remaining": YELP_MONTHLY_LIMIT - data.get("monthly_used", 0),
                "daily_used": data.get("daily_used", 0),
                "daily_remaining": YELP_DAILY_LIMIT - data.get("daily_used", 0),
                "monthly_limit": YELP_MONTHLY_LIMIT,
                "daily_limit": YELP_DAILY_LIMIT,
            }
    except Exception:
        pass

    duplicates = (await db.execute(
        select(func.count()).select_from(Lead).where(Lead.duplicate_of_id.isnot(None))
    )).scalar_one()
    dead_websites = (await db.execute(
        select(func.count()).select_from(Lead).where(Lead.website_status == "dead")
    )).scalar_one()
    phones_validated = (await db.execute(
        select(func.count()).select_from(Lead).where(Lead.phone_valid.isnot(None))
    )).scalar_one()
    phones_valid = (await db.execute(
        select(func.count()).select_from(Lead).where(Lead.phone_valid == True)  # noqa: E712
    )).scalar_one()

    return {
        "leads": {
            "total": total,
            "ai_scored": scored,
            "ai_scored_pct": round(scored / total * 100, 1) if total else 0,
            "with_yelp_rating": with_rating,
            "consumer_intent": consumer,
            "duplicates_marked": duplicates,
            "dead_websites": dead_websites,
            "phones_validated": phones_validated,
            "phones_valid": phones_valid,
            "phone_valid_pct": round(phones_valid / phones_validated * 100, 1) if phones_validated else 0,
        },
        "yelp_budget": yelp,
    }
