"""
Free sample download endpoint.
Returns 5 real leads as a CSV without requiring payment.
Rate-limited: one sample per email × industry × state combination.
Does NOT increment times_sold.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Lead, SampleRequest
from app.schemas import SampleRequestSchema
from app.services.csv_export import generate_csv
from app.services.geo import get_cities_in_radius, get_zip_info

FRESHNESS_DAYS = 180
SAMPLE_SIZE = 5

router = APIRouter()


@router.post("/leads/sample")
async def free_sample(body: SampleRequestSchema, db: AsyncSession = Depends(get_db)):
    email = body.email.strip().lower()
    industry_lower = body.industry.strip().lower()
    state = body.state.strip().upper() if body.state else ""

    # Rate limit: one sample per email+industry+state
    existing = (
        await db.execute(
            select(SampleRequest).where(
                func.lower(SampleRequest.email) == email,
                func.lower(SampleRequest.industry) == industry_lower,
                SampleRequest.state == state,
            )
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="You've already received a free sample for this search. Ready to buy the full list?",
        )

    # Resolve ZIP radius → cities
    radius_cities: list[str] = []
    city = body.city
    if body.zip_code:
        if body.radius_miles and body.radius_miles > 0:
            cities, inferred_state = get_cities_in_radius(body.zip_code, body.radius_miles)
            radius_cities = cities
            if not state and inferred_state:
                state = inferred_state
        else:
            info = get_zip_info(body.zip_code)
            if info:
                if not city:
                    city = info["city"]
                if not state:
                    state = info["state"]

    freshness_cutoff = datetime.utcnow() - timedelta(days=FRESHNESS_DAYS)
    filters = [
        func.lower(Lead.industry).contains(industry_lower),
        Lead.times_sold < 5,
        Lead.scraped_date >= freshness_cutoff,
    ]
    if state:
        filters.append(Lead.state == state)
    if radius_cities:
        filters.append(func.lower(Lead.city).in_([c.lower() for c in radius_cities]))
    elif city:
        filters.append(func.lower(Lead.city).contains(city.strip().lower()))
    if body.lead_type and body.lead_type in ("business", "consumer"):
        filters.append(Lead.lead_type == body.lead_type)

    stmt = select(Lead).where(*filters).order_by(Lead.scraped_date.desc()).limit(SAMPLE_SIZE)
    leads = (await db.execute(stmt)).scalars().all()

    if not leads:
        raise HTTPException(status_code=404, detail="No leads found for this search. Try broadening your criteria.")

    # Record the sample request
    sample = SampleRequest(email=email, industry=industry_lower, state=state)
    db.add(sample)
    await db.commit()

    industry_slug = body.industry.lower().replace(" ", "_")
    filename = f"sample_{industry_slug}_{state or 'US'}.csv"

    return StreamingResponse(
        generate_csv(list(leads)),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
