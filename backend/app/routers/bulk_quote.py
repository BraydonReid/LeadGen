"""
Bulk quote requests — for orders of 5,000+ leads.

POST /api/bulk-quote  — save request + notify owner + send confirmation to requester
"""
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class BulkQuoteBody(BaseModel):
    name: str
    email: str
    company: str | None = None
    industry: str
    state: str
    quantity: int
    notes: str | None = None


@router.post("/bulk-quote")
async def submit_bulk_quote(body: BulkQuoteBody, db: AsyncSession = Depends(get_db)):
    name = body.name.strip()
    email = body.email.strip().lower()
    company = body.company.strip() if body.company else ""
    industry = body.industry.strip()
    state = body.state.strip().upper()
    quantity = body.quantity
    notes = body.notes.strip() if body.notes else ""

    logger.info(f"[bulk_quote] {email} requested {quantity}x {industry} leads in {state}")

    if not settings.smtp_password:
        return {"received": True}

    from app.services.email_sender import send_email

    # Notify the owner
    owner_html = f"""
<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#1e293b;">
  <div style="background:#1e293b;padding:20px 28px;border-radius:12px 12px 0 0;">
    <span style="color:white;font-weight:900;font-size:18px;">New Bulk Quote Request</span>
  </div>
  <div style="background:#f8fafc;padding:32px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0;">
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <tr><td style="padding:8px 0;color:#64748b;width:120px;">Name</td><td style="font-weight:600;">{name}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Email</td><td><a href="mailto:{email}">{email}</a></td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Company</td><td>{company or "—"}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Industry</td><td>{industry}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">State</td><td>{state}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Quantity</td><td style="font-weight:700;color:#2563eb;">{quantity:,} leads</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;vertical-align:top;">Notes</td><td>{notes or "—"}</td></tr>
    </table>
  </div>
</div>"""

    # Confirmation to requester
    confirmation_html = f"""
<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;color:#1e293b;">
  <div style="background:#2563eb;padding:20px 28px;border-radius:12px 12px 0 0;">
    <span style="color:white;font-weight:900;font-size:20px;">Take Your Lead Today</span>
  </div>
  <div style="background:#f8fafc;padding:32px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0;">
    <h2 style="margin-top:0;color:#1e293b;">Quote request received!</h2>
    <p>Hi {name},</p>
    <p>We received your request for <strong>{quantity:,} {industry} leads in {state}</strong>.
       We&apos;ll send you a custom quote within 24 hours.</p>
    <p>In the meantime, you can browse smaller quantities immediately:</p>
    <p style="margin:24px 0;">
      <a href="{settings.frontend_url}/shop?industry={industry}&state={state}"
         style="background:#2563eb;color:white;padding:14px 28px;text-decoration:none;
                border-radius:8px;font-weight:bold;font-size:15px;display:inline-block;">
        Browse Available Leads →
      </a>
    </p>
    <p style="color:#64748b;font-size:13px;">— The Take Your Lead Today team</p>
  </div>
</div>"""

    try:
        await send_email(
            settings.smtp_from_email,
            f"Bulk quote request: {quantity:,} {industry} leads — {name} ({email})",
            owner_html,
        )
    except Exception as e:
        logger.warning(f"[bulk_quote] Owner notification failed: {e}")

    try:
        await send_email(email, "Your bulk quote request — Take Your Lead Today", confirmation_html)
    except Exception as e:
        logger.warning(f"[bulk_quote] Confirmation email failed: {e}")

    return {"received": True}
