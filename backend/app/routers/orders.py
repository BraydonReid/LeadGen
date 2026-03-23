"""
Order history lookup — email-based, no passwords required.
Buyers enter their email to see what they've already purchased and re-download.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Purchase

router = APIRouter()


@router.get("/orders")
async def get_orders(
    email: str = Query(..., description="Buyer email address"),
    db: AsyncSession = Depends(get_db),
):
    """Return fulfilled purchases for a given email address, newest first."""
    result = await db.execute(
        select(Purchase)
        .where(Purchase.buyer_email == email.lower().strip())
        .where(Purchase.fulfilled == True)  # noqa: E712
        .order_by(Purchase.created_at.desc())
    )
    purchases = result.scalars().all()

    return {
        "purchases": [
            {
                "id": p.id,
                "industry": p.industry,
                "state": p.state,
                "city": p.city,
                "quantity": p.quantity,
                "amount_dollars": round(p.amount_cents / 100, 2),
                "created_at": p.created_at.isoformat(),
                "stripe_session_id": p.stripe_session_id,
            }
            for p in purchases
        ]
    }
