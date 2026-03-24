from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Lead, Purchase
from app.services.csv_export import generate_csv
from app.services.leads import get_leads_for_download

router = APIRouter()


@router.get("/download")
async def download(
    session_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Purchase).where(Purchase.stripe_session_id == session_id)
    result = await db.execute(stmt)
    purchase = result.scalar_one_or_none()

    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    if not purchase.fulfilled:
        raise HTTPException(status_code=402, detail="Payment not yet confirmed. Please wait a moment and try again.")

    leads = await get_leads_for_download(
        db,
        industry=purchase.industry,
        state=purchase.state,
        city=purchase.city,
        quantity=purchase.quantity,
        zip_code=purchase.zip_code,
        radius_miles=float(purchase.radius_miles) if purchase.radius_miles else None,
    )

    # Increment times_sold for each delivered lead (skip for owner test account)
    OWNER_EMAILS = {"braydonreid01@gmail.com"}
    if leads and purchase.buyer_email not in OWNER_EMAILS:
        lead_ids = [l.id for l in leads]
        await db.execute(
            update(Lead)
            .where(Lead.id.in_(lead_ids))
            .values(times_sold=Lead.times_sold + 1)
        )
        await db.commit()

    industry_slug = purchase.industry.lower().replace(" ", "_")
    filename = f"leads_{industry_slug}_{purchase.state.upper()}.csv"

    return StreamingResponse(
        generate_csv(leads),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
