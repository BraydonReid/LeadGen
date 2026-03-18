from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.models import Lead
from app.schemas import IndustryStat, PricedLeadPreview, ShopResponse, SearchQuery, StatsResponse
from app.services.pricing import calculate_lead_price
from app.services.geo import get_cities_in_radius, get_zip_info

# Leads not refreshed within this window are considered stale and hidden from shop
FRESHNESS_DAYS = 180


router = APIRouter()


@router.get("/shop", response_model=ShopResponse)
async def shop_search(
    industry: str = Query(..., min_length=1),
    state: str = Query(default="", min_length=0, max_length=2),
    city: str | None = Query(default=None),
    lead_type: str | None = Query(default=None),
    zip_code: str | None = Query(default=None),
    radius_miles: float | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    industry_lower = industry.strip().lower()

    # ZIP radius mode: auto-detect state + expand to nearby cities
    radius_cities: list[str] = []
    if zip_code:
        if radius_miles and radius_miles > 0:
            cities_in_radius, inferred_state = get_cities_in_radius(zip_code, radius_miles)
            radius_cities = cities_in_radius
            if not state and inferred_state:
                state = inferred_state
        else:
            # No radius — just use the ZIP's own city/state
            info = get_zip_info(zip_code)
            if info:
                if not city:
                    city = info["city"]
                if not state:
                    state = info["state"]

    state_upper = state.strip().upper() if state else ""

    freshness_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=FRESHNESS_DAYS)
    filters = [
        func.lower(Lead.industry).contains(industry_lower),
        Lead.times_sold < 5,
        Lead.scraped_date >= freshness_cutoff,
    ]
    if state_upper:
        filters.append(Lead.state == state_upper)

    if radius_cities:
        # Radius mode: match any city in the expanded list
        filters.append(func.lower(Lead.city).in_([c.lower() for c in radius_cities]))
    elif city:
        filters.append(func.lower(Lead.city).contains(city.strip().lower()))

    if lead_type and lead_type in ("business", "consumer"):
        filters.append(Lead.lead_type == lead_type)

    # Total count
    count_stmt = select(func.count()).select_from(Lead).where(*filters)
    total_count = (await db.execute(count_stmt)).scalar_one()

    # Sample up to 100 leads to calculate avg price; prefer AI-scored leads first
    sample_stmt = (
        select(Lead)
        .where(*filters)
        .order_by(Lead.conversion_score.desc().nulls_last(), Lead.quality_score.desc().nulls_last())
        .limit(100)
    )
    sample_result = await db.execute(sample_stmt)
    sample_leads = sample_result.scalars().all()

    if not sample_leads:
        return ShopResponse(
            total_count=0,
            avg_lead_price=0.0,
            preview=[],
            query=SearchQuery(industry=industry, state=state_upper, city=city, lead_type=lead_type, zip_code=zip_code, radius_miles=radius_miles),
        )

    prices = [calculate_lead_price(l) for l in sample_leads]
    avg_lead_price = sum(prices) / len(prices)

    # Preview: first 10 with individual prices
    preview = [
        PricedLeadPreview(
            id=lead.id,
            business_name=lead.business_name,
            industry=lead.industry,
            city=lead.city,
            state=lead.state,
            website=lead.website,
            phone=lead.phone,
            quality_score=lead.quality_score,
            conversion_score=lead.conversion_score,
            lead_type=lead.lead_type or "business",
            full_address=lead.full_address,
            yelp_rating=lead.yelp_rating,
            review_count=lead.review_count,
            years_in_business=lead.years_in_business,
            unit_price=prices[i],
        )
        for i, lead in enumerate(sample_leads[:10])
    ]

    return ShopResponse(
        total_count=total_count,
        avg_lead_price=round(avg_lead_price, 4),
        preview=preview,
        query=SearchQuery(
            industry=industry,
            state=state_upper,
            city=city,
            lead_type=lead_type,
            zip_code=zip_code,
            radius_miles=radius_miles,
        ),
    )


@router.get("/shop/stats", response_model=StatsResponse)
async def shop_stats(db: AsyncSession = Depends(get_db)):
    freshness_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=FRESHNESS_DAYS)
    total_stmt = select(func.count()).select_from(Lead).where(
        Lead.times_sold < 5,
        Lead.scraped_date >= freshness_cutoff,
    )
    total_leads = (await db.execute(total_stmt)).scalar_one()

    consumer_stmt = select(func.count()).select_from(Lead).where(
        Lead.lead_type == "consumer",
        Lead.times_sold < 5,
        Lead.scraped_date >= freshness_cutoff,
    )
    consumer_count = (await db.execute(consumer_stmt)).scalar_one()

    industry_stmt = (
        select(Lead.industry, func.count().label("cnt"))
        .where(Lead.times_sold < 5)
        .group_by(Lead.industry)
        .order_by(func.count().desc())
        .limit(20)
    )
    rows = (await db.execute(industry_stmt)).all()
    industries = [IndustryStat(industry=r.industry.title(), count=r.cnt) for r in rows]

    return StatsResponse(
        total_leads=total_leads,
        consumer_intent_count=consumer_count,
        industries=industries,
    )
