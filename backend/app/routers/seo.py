"""
SEO data endpoints — used by Next.js landing pages for SSR/ISR.

GET /api/seo/pages          — all industry×city combos with lead counts (for sitemap)
GET /api/seo/page/{industry}/{city} — stats + sample leads for one landing page
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import Lead
from app.services.pricing import calculate_lead_price

router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class PageSummary(BaseModel):
    industry: str
    city: str
    state: str
    count: int
    slug_industry: str
    slug_city: str


class SampleLead(BaseModel):
    business_name: str
    city: str
    state: str
    quality_score: int | None
    yelp_rating: float | None
    review_count: int | None
    lead_type: str


class PageData(BaseModel):
    industry: str
    city: str
    state: str
    count: int
    avg_price: float
    sample_leads: list[SampleLead]
    related_industries: list[str]
    related_cities: list[str]


def _slugify(s: str) -> str:
    return s.lower().replace(" ", "-").replace("/", "-").replace(",", "")


@router.get("/seo/pages", response_model=list[PageSummary])
async def list_pages(min_count: int = 10, db: AsyncSession = Depends(get_db)):
    """
    Returns all industry×city combinations with at least min_count leads.
    Used to generate the sitemap and /leads directory page.
    """
    stmt = (
        select(Lead.industry, Lead.city, Lead.state, func.count(Lead.id).label("cnt"))
        .group_by(Lead.industry, Lead.city, Lead.state)
        .having(func.count(Lead.id) >= min_count)
        .order_by(func.count(Lead.id).desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        PageSummary(
            industry=r.industry,
            city=r.city,
            state=r.state,
            count=r.cnt,
            slug_industry=_slugify(r.industry),
            slug_city=_slugify(f"{r.city}-{r.state}"),
        )
        for r in rows
    ]


@router.get("/seo/page/{slug_industry}/{slug_city}", response_model=PageData)
async def page_data(slug_industry: str, slug_city: str, db: AsyncSession = Depends(get_db)):
    """
    Returns data for a single SEO landing page.
    slug_city format: "dallas-tx" or "houston-tx"
    """
    # Parse city/state from slug
    parts = slug_city.rsplit("-", 1)
    if len(parts) != 2:
        from fastapi import HTTPException
        raise HTTPException(404, "Invalid city slug")
    city_slug, state = parts[0].replace("-", " ").title(), parts[1].upper()
    industry = slug_industry.replace("-", " ")

    # Get count
    count_result = await db.execute(
        select(func.count(Lead.id))
        .where(func.lower(Lead.industry) == industry.lower())
        .where(func.lower(Lead.city) == city_slug.lower())
        .where(Lead.state == state)
    )
    count = count_result.scalar() or 0

    # Get sample leads (no contact info — just enough for SEO social proof)
    sample_result = await db.execute(
        select(Lead)
        .where(func.lower(Lead.industry) == industry.lower())
        .where(func.lower(Lead.city) == city_slug.lower())
        .where(Lead.state == state)
        .order_by(Lead.quality_score.desc().nullslast())
        .limit(5)
    )
    samples = sample_result.scalars().all()
    avg_price = round(
        sum(calculate_lead_price(l) for l in samples) / len(samples), 2
    ) if samples else 0.25

    # Related industries in same city
    rel_ind_result = await db.execute(
        select(Lead.industry, func.count(Lead.id).label("cnt"))
        .where(func.lower(Lead.city) == city_slug.lower())
        .where(Lead.state == state)
        .group_by(Lead.industry)
        .order_by(func.count(Lead.id).desc())
        .limit(8)
    )
    related_industries = [r.industry for r in rel_ind_result.all() if r.industry.lower() != industry.lower()][:6]

    # Related cities for same industry
    rel_city_result = await db.execute(
        select(Lead.city, Lead.state, func.count(Lead.id).label("cnt"))
        .where(func.lower(Lead.industry) == industry.lower())
        .group_by(Lead.city, Lead.state)
        .order_by(func.count(Lead.id).desc())
        .limit(8)
    )
    related_cities = [
        f"{r.city}, {r.state}" for r in rel_city_result.all()
        if r.city.lower() != city_slug.lower()
    ][:6]

    return PageData(
        industry=industry.title(),
        city=city_slug,
        state=state,
        count=count,
        avg_price=avg_price,
        sample_leads=[
            SampleLead(
                business_name=l.business_name,
                city=l.city,
                state=l.state,
                quality_score=l.quality_score,
                yelp_rating=l.yelp_rating,
                review_count=l.review_count,
                lead_type=l.lead_type,
            )
            for l in samples
        ],
        related_industries=related_industries,
        related_cities=related_cities,
    )
