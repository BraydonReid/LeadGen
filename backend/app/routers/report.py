"""
Bad lead report endpoint.
Buyers report bad leads from a fulfilled purchase and receive a store credit code.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import LeadCredit, Purchase
from app.schemas import LeadReportRequest, LeadReportResponse

router = APIRouter()

# Cap credits at 10% of purchase amount
CREDIT_PCT = 0.10
MIN_DISCOUNT_CENTS = 50  # $0.50 minimum credit


@router.get("/credits/{code}")
async def validate_credit(code: str, db: AsyncSession = Depends(get_db)):
    """Lightweight credit code validation for frontend display."""
    credit = (
        await db.execute(select(LeadCredit).where(LeadCredit.code == code.strip().upper()))
    ).scalar_one_or_none()
    if not credit or credit.used:
        raise HTTPException(status_code=404, detail="Invalid or already-used promo code")
    return {"valid": True, "discount_dollars": round(credit.discount_cents / 100, 2)}


@router.post("/leads/report", response_model=LeadReportResponse)
async def report_leads(body: LeadReportRequest, db: AsyncSession = Depends(get_db)):
    # Validate purchase exists and is fulfilled
    stmt = select(Purchase).where(Purchase.stripe_session_id == body.session_id)
    purchase = (await db.execute(stmt)).scalar_one_or_none()

    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    if not purchase.fulfilled:
        raise HTTPException(status_code=400, detail="Purchase not yet fulfilled")

    # One report per purchase
    existing = (
        await db.execute(
            select(LeadCredit).where(LeadCredit.session_id == body.session_id)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="A credit has already been issued for this purchase",
        )

    # Calculate credit: 10% of purchase, min $0.50
    discount_cents = max(MIN_DISCOUNT_CENTS, int(purchase.amount_cents * CREDIT_PCT))

    # Generate unique code
    code = f"CRED-{secrets.token_hex(4).upper()}"

    credit = LeadCredit(
        code=code,
        discount_cents=discount_cents,
        session_id=body.session_id,
        used=False,
    )
    db.add(credit)
    await db.commit()

    return LeadReportResponse(
        credit_code=code,
        discount_amount_dollars=round(discount_cents / 100, 2),
    )
