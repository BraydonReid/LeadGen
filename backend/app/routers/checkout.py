from datetime import datetime, timedelta, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Lead, LeadCredit, Purchase
from app.schemas import CheckoutRequest, CheckoutResponse
from app.services.pricing import calculate_lead_price, calculate_purchase_total
from app.services.geo import get_cities_in_radius, get_zip_info

stripe.api_key = settings.stripe_secret_key

router = APIRouter()

FRONTEND_URL = settings.frontend_url


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    body: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
):
    if body.quantity < 1:
        raise HTTPException(status_code=400, detail="quantity must be at least 1")

    industry_lower = body.industry.strip().lower()
    state = body.state or ""

    # ZIP radius expansion
    radius_cities: list[str] = []
    city = body.city
    if body.zip_code:
        if body.radius_miles and body.radius_miles > 0:
            cities_in_radius, inferred_state = get_cities_in_radius(body.zip_code, body.radius_miles)
            radius_cities = cities_in_radius
            if not state and inferred_state:
                state = inferred_state
        else:
            info = get_zip_info(body.zip_code)
            if info:
                if not city:
                    city = info["city"]
                if not state:
                    state = info["state"]

    state_upper = state.strip().upper() if state else ""

    freshness_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=180)
    filters = [
        func.lower(Lead.industry).contains(industry_lower),
        Lead.times_sold < 5,
        Lead.scraped_date >= freshness_cutoff,
    ]
    if state_upper:
        filters.append(Lead.state == state_upper)

    if radius_cities:
        filters.append(func.lower(Lead.city).in_([c.lower() for c in radius_cities]))
    elif city:
        filters.append(func.lower(Lead.city).contains(city.strip().lower()))

    if body.lead_type and body.lead_type in ("business", "consumer"):
        filters.append(Lead.lead_type == body.lead_type)

    count_stmt = select(func.count()).select_from(Lead).where(*filters)
    available = (await db.execute(count_stmt)).scalar_one()

    if available == 0:
        raise HTTPException(status_code=400, detail="No leads available for this search")

    actual_quantity = min(body.quantity, available)

    sample_stmt = (
        select(Lead)
        .where(*filters)
        .order_by(Lead.conversion_score.desc().nulls_last(), Lead.quality_score.desc().nulls_last())
        .limit(min(100, actual_quantity))
    )
    sample = (await db.execute(sample_stmt)).scalars().all()
    avg_price = sum(calculate_lead_price(l) for l in sample) / len(sample)

    pricing = calculate_purchase_total(avg_price, actual_quantity)
    amount_cents = max(50, int(pricing["total"] * 100))

    # Apply promo / store credit code
    credit_discount_cents = 0
    credit: LeadCredit | None = None
    if body.promo_code:
        credit = (
            await db.execute(
                select(LeadCredit).where(LeadCredit.code == body.promo_code.strip().upper())
            )
        ).scalar_one_or_none()
        if not credit:
            raise HTTPException(status_code=400, detail="Invalid promo code")
        if credit.used:
            raise HTTPException(status_code=400, detail="This promo code has already been used")
        credit_discount_cents = credit.discount_cents
        amount_cents = max(50, amount_cents - credit_discount_cents)

    industry_label = body.industry.title()
    state_label = (body.state or state_upper).upper()

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": amount_cents,
                    "product_data": {
                        "name": f"{actual_quantity:,} {industry_label} Business Leads — {state_label}",
                        "description": (
                            f"Instant CSV download. ${avg_price:.2f} avg/lead, "
                            f"{pricing['discount_pct']}% bulk discount applied."
                        ),
                    },
                },
                "quantity": 1,
            }
        ],
        metadata={
            "industry": body.industry,
            "state": body.state,
            "city": body.city or "",
            "quantity": str(actual_quantity),
            "lead_type": body.lead_type or "all",
        },
        success_url=f"{FRONTEND_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{FRONTEND_URL}/shop?industry={body.industry}&state={body.state}",
    )

    # Mark credit used now that a session has been created
    if credit:
        credit.used = True

    purchase = Purchase(
        stripe_session_id=session.id,
        industry=body.industry,
        state=state_upper,
        city=city,
        quantity=actual_quantity,
        amount_cents=amount_cents,
        avg_lead_price_cents=int(avg_price * 100),
        discount_pct=pricing["discount_pct"],
        fulfilled=False,
        zip_code=body.zip_code,
        radius_miles=int(body.radius_miles) if body.radius_miles else None,
        utm_source=body.utm_source,
        utm_medium=body.utm_medium,
        utm_campaign=body.utm_campaign,
        referrer=body.referrer,
    )
    db.add(purchase)
    await db.commit()

    return CheckoutResponse(
        checkout_url=session.url,
        total=pricing["total"],
        discount_pct=pricing["discount_pct"],
        avg_lead_price=round(avg_price, 4),
    )
