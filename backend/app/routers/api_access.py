"""
Programmatic lead access for Pro/Agency subscribers.

Authentication: Authorization: Bearer {api_key}
  GET /api/leads — query leads, returns JSON, deducts credits

Usage:
  curl -H "Authorization: Bearer {api_key}" \
       "https://api.takeyourleadtoday.com/api/leads?industry=hvac&state=TX&limit=50"
"""
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Lead, Subscription, SubscriptionDownload
from app.services.leads import get_leads_for_download

logger = logging.getLogger(__name__)
router = APIRouter()


async def _require_api_key(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Subscription:
    """Dependency: validates Bearer API key, returns active Pro/Agency subscription."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="API key required. Use: Authorization: Bearer {api_key}",
        )
    api_key = authorization.removeprefix("Bearer ").strip()
    result = await db.execute(
        select(Subscription)
        .where(Subscription.api_key == api_key)
        .where(Subscription.status == "active")
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key.")
    if sub.plan not in ("pro", "agency"):
        raise HTTPException(status_code=403, detail="API access requires a Pro or Agency subscription.")
    return sub


@router.get("/leads")
async def get_leads_api(
    industry: str = Query(..., description="Industry name (e.g. hvac, roofing, plumbing)"),
    state: str = Query(..., description="2-letter state code (e.g. TX)"),
    city: str | None = Query(None, description="City name (optional)"),
    limit: int = Query(default=50, ge=1, le=500, description="Max leads to return (1–500)"),
    sub: Subscription = Depends(_require_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch leads as JSON. Deducts credits from your subscription.
    Returns up to `limit` leads (capped at your remaining credits).
    """
    total_credits = sub.credits_remaining + sub.rollover_credits
    if total_credits <= 0:
        raise HTTPException(
            status_code=403,
            detail="No credits remaining. Resets on your next billing date.",
        )

    quantity = min(limit, total_credits, sub.leads_per_month)
    leads = await get_leads_for_download(db, industry=industry, state=state, city=city, quantity=quantity)
    if not leads:
        return {"leads": [], "credits_used": 0, "credits_remaining": total_credits}

    actual = len(leads)

    OWNER_EMAILS = set(settings.owner_emails)
    if sub.buyer_email not in OWNER_EMAILS:
        lead_ids = [lead.id for lead in leads]
        await db.execute(
            sa_update(Lead).where(Lead.id.in_(lead_ids)).values(times_sold=Lead.times_sold + 1)
        )

    if sub.rollover_credits >= actual:
        sub.rollover_credits = max(0, sub.rollover_credits - actual)
    else:
        remaining = actual - sub.rollover_credits
        sub.rollover_credits = 0
        sub.credits_remaining = max(0, sub.credits_remaining - remaining)

    db.add(SubscriptionDownload(
        subscription_id=sub.id,
        industry=industry,
        state=state.upper(),
        city=city,
        quantity=actual,
    ))
    await db.commit()

    credits_left = sub.credits_remaining + sub.rollover_credits
    logger.info(f"[api_access] {sub.buyer_email} fetched {actual} {industry}/{state} leads via API")

    return {
        "leads": [
            {
                "id": lead.id,
                "business_name": lead.business_name,
                "contact_name": lead.contact_name,
                "contact_title": lead.contact_title,
                "industry": lead.industry,
                "city": lead.city,
                "state": lead.state,
                "zip_code": lead.zip_code,
                "full_address": lead.full_address,
                "phone": lead.phone,
                "email": lead.email,
                "email_verified": lead.email_verified,
                "website": lead.website,
                "linkedin_url": lead.linkedin_url,
                "facebook_url": lead.facebook_url,
                "instagram_url": lead.instagram_url,
                "yelp_rating": lead.yelp_rating,
                "review_count": lead.review_count,
                "conversion_score": lead.conversion_score,
                "bbb_rating": lead.bbb_rating,
                "bbb_accredited": lead.bbb_accredited,
                "lead_type": lead.lead_type,
                "scraped_date": lead.scraped_date.isoformat() if lead.scraped_date else None,
            }
            for lead in leads
        ],
        "credits_used": actual,
        "credits_remaining": credits_left,
    }
