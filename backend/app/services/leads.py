from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead
from app.schemas import LeadPreview, SearchQuery, SearchResponse
from app.services.geo import get_cities_in_radius, get_zip_info

FRESHNESS_DAYS = 365


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def search_leads(
    db: AsyncSession,
    industry: str,
    state: str,
    city: str | None = None,
) -> SearchResponse:
    industry_lower = industry.strip().lower()
    state_upper = state.strip().upper()
    freshness_cutoff = _now() - timedelta(days=FRESHNESS_DAYS)

    filters = [
        func.lower(Lead.industry).contains(industry_lower),
        Lead.state == state_upper,
        Lead.scraped_date >= freshness_cutoff,
        Lead.duplicate_of_id.is_(None),
        Lead.archived == False,  # noqa: E712
    ]
    if city:
        filters.append(func.lower(Lead.city).contains(city.strip().lower()))

    count_stmt = select(func.count()).select_from(Lead).where(*filters)
    total_count = (await db.execute(count_stmt)).scalar_one()

    preview_stmt = (
        select(Lead)
        .where(*filters)
        .order_by(Lead.conversion_score.desc().nulls_last(), Lead.quality_score.desc().nulls_last())
        .limit(10)
    )
    result = await db.execute(preview_stmt)
    leads = result.scalars().all()

    return SearchResponse(
        total_count=total_count,
        preview=[LeadPreview.model_validate(lead) for lead in leads],
        query=SearchQuery(industry=industry, state=state, city=city, lead_type=None),
    )


async def get_leads_for_download(
    db: AsyncSession,
    industry: str,
    state: str,
    city: str | None,
    quantity: int,
    zip_code: str | None = None,
    radius_miles: float | None = None,
) -> list[Lead]:
    freshness_cutoff = _now() - timedelta(days=FRESHNESS_DAYS)

    # ZIP radius expansion
    radius_cities: list[str] = []
    resolved_city = city
    resolved_state = state
    if zip_code:
        if radius_miles and radius_miles > 0:
            cities, inferred_state = get_cities_in_radius(zip_code, radius_miles)
            radius_cities = cities
            if not resolved_state and inferred_state:
                resolved_state = inferred_state
        else:
            info = get_zip_info(zip_code)
            if info:
                if not resolved_city:
                    resolved_city = info["city"]
                if not resolved_state:
                    resolved_state = info["state"]

    filters = [
        func.lower(Lead.industry).contains(industry.strip().lower()),
        Lead.times_sold < 5,
        Lead.scraped_date >= freshness_cutoff,
        Lead.duplicate_of_id.is_(None),
        Lead.archived == False,  # noqa: E712
    ]
    if resolved_state:
        filters.append(Lead.state == resolved_state.strip().upper())

    if radius_cities:
        filters.append(func.lower(Lead.city).in_([c.lower() for c in radius_cities]))
    elif resolved_city:
        filters.append(func.lower(Lead.city).contains(resolved_city.strip().lower()))

    # Deliver best leads first: highest conversion score, then quality, then freshness
    stmt = (
        select(Lead)
        .where(*filters)
        .order_by(
            Lead.conversion_score.desc().nulls_last(),
            Lead.quality_score.desc().nulls_last(),
            Lead.scraped_date.desc(),
        )
        .limit(quantity)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
