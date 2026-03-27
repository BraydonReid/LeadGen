"""
Industry demand waitlist — visitors request industries we don't have yet.

POST /api/industry-request  — save request + send confirmation email
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import IndustryRequest

logger = logging.getLogger(__name__)
router = APIRouter()


class IndustryRequestBody(BaseModel):
    email: str
    industry: str
    state: str
    city: str | None = None


@router.post("/industry-request")
async def submit_industry_request(body: IndustryRequestBody, db: AsyncSession = Depends(get_db)):
    email = body.email.strip().lower()
    industry = body.industry.strip().lower()
    state = body.state.strip().upper()[:2]
    city = body.city.strip() if body.city else None

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required.")
    if not industry:
        raise HTTPException(status_code=400, detail="Industry name required.")
    if len(state) != 2:
        raise HTTPException(status_code=400, detail="Valid 2-letter state code required.")

    existing = await db.execute(
        select(IndustryRequest)
        .where(IndustryRequest.email == email)
        .where(IndustryRequest.industry == industry)
        .where(IndustryRequest.state == state)
    )
    if existing.scalar_one_or_none():
        return {"saved": True, "already_requested": True}

    req = IndustryRequest(email=email, industry=industry, state=state, city=city)
    db.add(req)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return {"saved": True, "already_requested": True}

    logger.info(f"[industry_request] {email} requested {industry} in {state}")

    if settings.smtp_password:
        from app.services.email_sender import send_email
        location = f"{city}, {state}" if city else state
        html = f"""
<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;color:#1e293b;">
  <div style="background:#2563eb;padding:20px 28px;border-radius:12px 12px 0 0;">
    <span style="color:white;font-weight:900;font-size:20px;">Take Your Lead Today</span>
  </div>
  <div style="background:#f8fafc;padding:32px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0;">
    <h2 style="margin-top:0;color:#1e293b;">We got your request!</h2>
    <p>Thanks for requesting <strong>{industry.title()}</strong> leads in <strong>{location}</strong>.</p>
    <p>We&apos;ll notify you as soon as we have leads matching your request. Most requests are
       fulfilled within 1–2 weeks.</p>
    <p>In the meantime, browse what&apos;s available now:</p>
    <p style="margin:24px 0;">
      <a href="{settings.frontend_url}/shop"
         style="background:#2563eb;color:white;padding:14px 28px;text-decoration:none;
                border-radius:8px;font-weight:bold;font-size:15px;display:inline-block;">
        Browse Available Leads →
      </a>
    </p>
  </div>
</div>"""
        try:
            await send_email(email, f"Request received: {industry.title()} leads in {location}", html)
        except Exception as e:
            logger.warning(f"[industry_request] Confirmation email failed: {e}")

    return {"saved": True, "already_requested": False}
