import logging

import stripe
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import IndustryDemand, Purchase, Subscription

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    # Must read raw bytes BEFORE any JSON parsing for signature verification
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        if obj.get("mode") == "subscription":
            from app.routers.subscriptions import handle_subscription_created
            async with AsyncSessionLocal() as db:
                await handle_subscription_created(obj, db)
        else:
            await _fulfill_purchase(obj)

    elif event_type == "invoice.payment_succeeded":
        from app.routers.subscriptions import handle_invoice_paid
        async with AsyncSessionLocal() as db:
            await handle_invoice_paid(obj, db)

    elif event_type == "customer.subscription.deleted":
        from app.routers.subscriptions import handle_subscription_canceled
        async with AsyncSessionLocal() as db:
            await handle_subscription_canceled(obj, db)

    elif event_type == "invoice.payment_failed":
        from app.routers.subscriptions import handle_invoice_failed
        async with AsyncSessionLocal() as db:
            await handle_invoice_failed(obj, db)

    return {"status": "ok"}


async def _fulfill_purchase(session: dict):
    stripe_session_id = session["id"]
    buyer_email = (session.get("customer_details") or {}).get("email")

    async with AsyncSessionLocal() as db:
        stmt = select(Purchase).where(Purchase.stripe_session_id == stripe_session_id)
        result = await db.execute(stmt)
        purchase = result.scalar_one_or_none()

        if purchase and not purchase.fulfilled:
            purchase.fulfilled = True
            if buyer_email and not purchase.buyer_email:
                purchase.buyer_email = buyer_email
            await db.commit()

            # Send purchase confirmation email
            if buyer_email and settings.smtp_password:
                try:
                    from app.services.email_sender import send_email
                    download_url = f"{settings.frontend_url}/success?session_id={stripe_session_id}"
                    industry_label = (purchase.industry or "").title()
                    state_label = purchase.state or ""
                    total_dollars = f"${purchase.amount_cents / 100:.2f}"
                    html = f"""
<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;color:#1e293b;">
  <div style="background:#2563eb;padding:20px 28px;border-radius:12px 12px 0 0;">
    <span style="color:white;font-weight:900;font-size:20px;">Take Your Lead Today</span>
  </div>
  <div style="background:#f8fafc;padding:32px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0;">
    <h2 style="margin-top:0;color:#1e293b;">Your {purchase.quantity:,} leads are ready to download</h2>
    <p style="color:#475569;">Thanks for your purchase of <strong>{purchase.quantity:,} {industry_label} leads
    {f'in {state_label}' if state_label else ''}</strong> ({total_dollars}).</p>
    <p style="margin:28px 0;">
      <a href="{download_url}"
         style="background:#2563eb;color:white;padding:14px 28px;text-decoration:none;
                border-radius:8px;font-weight:bold;font-size:15px;display:inline-block;">
        Download My Leads (CSV) →
      </a>
    </p>
    <p style="color:#475569;font-size:14px;">
      Save this email — the download link works anytime. If you have questions,
      reply to this email and we'll help.
    </p>
    <p style="font-size:12px;color:#94a3b8;">
      Take Your Lead Today &bull; <a href="{settings.frontend_url}" style="color:#94a3b8;">{settings.frontend_url}</a>
    </p>
  </div>
</div>"""
                    await send_email(buyer_email, f"Your {purchase.quantity:,} {industry_label} leads are ready", html)
                except Exception as e:
                    logger.warning(f"[webhook] Purchase confirmation email failed: {e}")

            # Update demand tracking so scraper can prioritize what sells
            try:
                state_code = (purchase.state or "")[:2].upper()
                await db.execute(
                    pg_insert(IndustryDemand)
                    .values(
                        industry=purchase.industry,
                        state=state_code,
                        city=purchase.city,
                        purchase_count=1,
                        leads_sold=purchase.quantity,
                        revenue_cents=purchase.amount_cents,
                    )
                    .on_conflict_do_update(
                        constraint="uq_demand_industry_state_city",
                        set_={
                            "purchase_count": IndustryDemand.purchase_count + 1,
                            "leads_sold": IndustryDemand.leads_sold + purchase.quantity,
                            "revenue_cents": IndustryDemand.revenue_cents + purchase.amount_cents,
                        },
                    )
                )
                await db.commit()
            except Exception as e:
                logger.warning(f"[webhook] Demand tracking failed for session {stripe_session_id}: {e}")
