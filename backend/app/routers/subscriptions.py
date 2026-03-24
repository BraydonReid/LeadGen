"""
Subscription management — $99/month Pro plan (300 leads/month).

Authentication: magic link emails. No passwords.
  POST /api/subscription/auth/request   — send sign-in link
  GET  /api/subscription/auth/verify    — exchange token for session

Subscription:
  POST /api/subscribe                   — create Stripe subscription checkout
  GET  /api/subscription/status         — plan info + credits (requires session)
  POST /api/subscription/download       — spend credits, get CSV (requires session)
  GET  /api/subscription/history        — past downloads (requires session)

Referral:
  GET  /api/subscription/referral       — get your referral link + stats (requires session)
  POST /api/subscription/referral/apply — apply a referral code to your subscription
"""
import logging
import os
import secrets
import string
from datetime import datetime, timedelta, timezone

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import (
    Subscription,
    SubscriptionDownload,
    SubscriptionMagicLink,
    SubscriptionSession,
)
from app.services.leads import get_leads_for_download
from app.services.csv_export import generate_csv

logger = logging.getLogger(__name__)
router = APIRouter()

stripe.api_key = settings.stripe_secret_key
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

PLAN_PRICE_CENTS = 9900
PLAN_LEADS = 300
PLAN_NAME = "LeadGen Pro — 300 leads/month"
PLAN_DESCRIPTION = "300 fresh leads every month. Any industry, any state. Cancel anytime."

MAGIC_LINK_TTL_MINUTES = 20
SESSION_TTL_DAYS = 7
REFERRAL_BONUS_CREDITS = 50


# ── Auth dependency ────────────────────────────────────────────────────────────

async def require_session(
    x_sub_session: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> str:
    """Dependency: validates session token, returns subscriber email."""
    if not x_sub_session:
        raise HTTPException(status_code=401, detail="Sign-in required. Visit /my-subscription to authenticate.")
    result = await db.execute(
        select(SubscriptionSession)
        .where(SubscriptionSession.token == x_sub_session)
        .where(SubscriptionSession.expires_at > datetime.utcnow())
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    return session.email


# ── Magic link ────────────────────────────────────────────────────────────────

class AuthRequest(BaseModel):
    email: str


@router.post("/subscription/auth/request")
async def request_magic_link(body: AuthRequest, db: AsyncSession = Depends(get_db)):
    """Send a magic sign-in link to the subscriber's email."""
    email = body.email.strip().lower()

    # Check subscription exists (active or canceled — allow canceled to view history)
    sub = await _get_any_sub(email, db)
    if not sub:
        # Don't reveal whether email is subscribed — just say "check your email"
        return {"sent": True}

    token = secrets.token_urlsafe(48)
    expires = datetime.utcnow() + timedelta(minutes=MAGIC_LINK_TTL_MINUTES)

    db.add(SubscriptionMagicLink(token=token, email=email, expires_at=expires))
    await db.commit()

    verify_url = f"{FRONTEND_URL}/subscription-verify?token={token}"

    # Send via Resend
    if settings.resend_api_key:
        from app.services.email_sender import send_email
        html = f"""
<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;color:#1e293b;">
  <div style="background:#2563eb;padding:20px 28px;border-radius:12px 12px 0 0;">
    <span style="color:white;font-weight:900;font-size:20px;">Take Your Lead Today</span>
  </div>
  <div style="background:#f8fafc;padding:32px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0;">
    <h2 style="margin-top:0;color:#1e293b;">Sign in to your subscription</h2>
    <p>Click the button below to access your subscriber portal. This link expires in {MAGIC_LINK_TTL_MINUTES} minutes.</p>
    <p style="margin:28px 0;">
      <a href="{verify_url}"
         style="background:#2563eb;color:white;padding:14px 28px;text-decoration:none;
                border-radius:8px;font-weight:bold;font-size:15px;display:inline-block;">
        Sign In to My Subscription →
      </a>
    </p>
    <p style="font-size:12px;color:#94a3b8;">
      If you didn't request this, you can safely ignore this email.<br>
      Link expires at {expires.strftime('%I:%M %p UTC')}.
    </p>
  </div>
</div>"""
        await send_email(email, "Sign in to Take Your Lead Today", html)

    return {"sent": True}


@router.get("/subscription/auth/verify")
async def verify_magic_link(token: str = Query(...), db: AsyncSession = Depends(get_db)):
    """Exchange a magic link token for a session token."""
    result = await db.execute(
        select(SubscriptionMagicLink)
        .where(SubscriptionMagicLink.token == token)
        .where(SubscriptionMagicLink.used == False)  # noqa: E712
        .where(SubscriptionMagicLink.expires_at > datetime.utcnow())
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=400, detail="This link has expired or already been used.")

    link.used = True

    session_token = secrets.token_urlsafe(48)
    session_expires = datetime.utcnow() + timedelta(days=SESSION_TTL_DAYS)
    db.add(SubscriptionSession(
        token=session_token,
        email=link.email,
        expires_at=session_expires,
    ))
    await db.commit()

    return {"session_token": session_token, "email": link.email}


# ── Checkout ──────────────────────────────────────────────────────────────────

class SubscribeRequest(BaseModel):
    email: str
    referral_code: str | None = None


@router.post("/subscribe")
async def create_subscription_checkout(body: SubscribeRequest):
    """Create a Stripe subscription checkout session."""
    session = stripe.checkout.Session.create(
        mode="subscription",
        payment_method_types=["card"],
        customer_email=body.email.strip().lower(),
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": PLAN_PRICE_CENTS,
                    "recurring": {"interval": "month"},
                    "product_data": {
                        "name": PLAN_NAME,
                        "description": PLAN_DESCRIPTION,
                    },
                },
                "quantity": 1,
            }
        ],
        metadata={
            "plan": "pro",
            "leads_per_month": str(PLAN_LEADS),
            "referral_code": body.referral_code or "",
        },
        success_url=f"{FRONTEND_URL}/my-subscription?subscribed=1",
        cancel_url=f"{FRONTEND_URL}/pricing",
    )
    return {"checkout_url": session.url}


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/subscription/status")
async def subscription_status(
    email: str = Depends(require_session),
    db: AsyncSession = Depends(get_db),
):
    sub = await _get_active_sub(email, db)
    if not sub:
        return {"subscribed": False}

    return {
        "subscribed": True,
        "status": sub.status,
        "plan": sub.plan,
        "leads_per_month": sub.leads_per_month,
        "credits_remaining": sub.credits_remaining,
        "rollover_credits": sub.rollover_credits,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "created_at": sub.created_at.isoformat(),
    }


# ── Download ──────────────────────────────────────────────────────────────────

class DownloadRequest(BaseModel):
    industry: str
    state: str
    city: str | None = None
    quantity: int


@router.post("/subscription/download")
async def subscription_download(
    body: DownloadRequest,
    email: str = Depends(require_session),
    db: AsyncSession = Depends(get_db),
):
    sub = await _get_active_sub(email, db)
    if not sub:
        raise HTTPException(status_code=403, detail="No active subscription found.")

    total_credits = sub.credits_remaining + sub.rollover_credits
    if total_credits <= 0:
        raise HTTPException(
            status_code=403,
            detail=f"No credits remaining. Resets on {sub.current_period_end.strftime('%B %d') if sub.current_period_end else 'next billing date'}.",
        )

    quantity = min(body.quantity, total_credits, sub.leads_per_month)
    if quantity < 1:
        raise HTTPException(status_code=400, detail="Quantity must be at least 1.")

    leads = await get_leads_for_download(
        db, industry=body.industry, state=body.state, city=body.city, quantity=quantity,
    )
    if not leads:
        raise HTTPException(status_code=404, detail="No leads found matching that search.")

    actual = len(leads)

    # Spend rollover first, then regular credits
    if sub.rollover_credits >= actual:
        sub.rollover_credits = max(0, sub.rollover_credits - actual)
    else:
        remaining_after_rollover = actual - sub.rollover_credits
        sub.rollover_credits = 0
        sub.credits_remaining = max(0, sub.credits_remaining - remaining_after_rollover)

    dl = SubscriptionDownload(
        subscription_id=sub.id,
        industry=body.industry,
        state=body.state.upper(),
        city=body.city,
        quantity=actual,
    )
    db.add(dl)
    await db.commit()

    slug = body.industry.lower().replace(" ", "_")
    filename = f"leads_{slug}_{body.state.upper()}.csv"

    return StreamingResponse(
        generate_csv(leads),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── History ───────────────────────────────────────────────────────────────────

@router.get("/subscription/history")
async def subscription_history(
    email: str = Depends(require_session),
    db: AsyncSession = Depends(get_db),
):
    sub = await _get_sub_by_email(email, db)
    if not sub:
        return {"downloads": []}

    result = await db.execute(
        select(SubscriptionDownload)
        .where(SubscriptionDownload.subscription_id == sub.id)
        .order_by(SubscriptionDownload.downloaded_at.desc())
        .limit(50)
    )
    downloads = result.scalars().all()

    return {
        "downloads": [
            {
                "industry": d.industry,
                "state": d.state,
                "city": d.city,
                "quantity": d.quantity,
                "downloaded_at": d.downloaded_at.isoformat(),
            }
            for d in downloads
        ]
    }


# ── Referral ──────────────────────────────────────────────────────────────────

@router.get("/subscription/referral")
async def get_referral_info(
    email: str = Depends(require_session),
    db: AsyncSession = Depends(get_db),
):
    """Return this subscriber's referral code + stats."""
    sub = await _get_active_sub(email, db)
    if not sub:
        raise HTTPException(status_code=403, detail="No active subscription.")

    if not sub.referral_code:
        sub.referral_code = _generate_referral_code()
        await db.commit()

    # Count referrals
    result = await db.execute(
        select(Subscription)
        .where(Subscription.referred_by_code == sub.referral_code)
        .where(Subscription.status == "active")
    )
    referrals = result.scalars().all()

    return {
        "referral_code": sub.referral_code,
        "referral_url": f"{FRONTEND_URL}/subscribe?ref={sub.referral_code}",
        "referrals_count": len(referrals),
        "bonus_credits_earned": len(referrals) * REFERRAL_BONUS_CREDITS,
    }


class ApplyReferralRequest(BaseModel):
    referral_code: str


@router.post("/subscription/referral/apply")
async def apply_referral(
    body: ApplyReferralRequest,
    email: str = Depends(require_session),
    db: AsyncSession = Depends(get_db),
):
    """Apply a referral code after subscription. Both parties get bonus credits."""
    sub = await _get_active_sub(email, db)
    if not sub:
        raise HTTPException(status_code=403, detail="No active subscription.")
    if sub.referred_by_code:
        raise HTTPException(status_code=400, detail="A referral code has already been applied.")

    code = body.referral_code.strip().upper()
    referrer_result = await db.execute(
        select(Subscription).where(Subscription.referral_code == code)
    )
    referrer = referrer_result.scalar_one_or_none()
    if not referrer or referrer.buyer_email == email:
        raise HTTPException(status_code=400, detail="Invalid referral code.")

    sub.referred_by_code = code
    sub.credits_remaining = min(
        sub.credits_remaining + REFERRAL_BONUS_CREDITS,
        sub.leads_per_month * 2,
    )
    referrer.credits_remaining = min(
        referrer.credits_remaining + REFERRAL_BONUS_CREDITS,
        referrer.leads_per_month * 2,
    )
    await db.commit()
    logger.info(f"[referral] {email} used code {code} — both parties got {REFERRAL_BONUS_CREDITS} credits")

    return {"applied": True, "bonus_credits": REFERRAL_BONUS_CREDITS}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_active_sub(email: str, db: AsyncSession) -> Subscription | None:
    result = await db.execute(
        select(Subscription)
        .where(Subscription.buyer_email == email.strip().lower())
        .where(Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
    )
    return result.scalars().first()


async def _get_sub_by_email(email: str, db: AsyncSession) -> Subscription | None:
    result = await db.execute(
        select(Subscription)
        .where(Subscription.buyer_email == email.strip().lower())
        .order_by(Subscription.created_at.desc())
    )
    return result.scalars().first()


async def _get_any_sub(email: str, db: AsyncSession) -> Subscription | None:
    result = await db.execute(
        select(Subscription)
        .where(Subscription.buyer_email == email.strip().lower())
        .order_by(Subscription.created_at.desc())
    )
    return result.scalars().first()


def _generate_referral_code() -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(7))


# ── Called from webhook ───────────────────────────────────────────────────────

async def handle_subscription_created(session: dict, db: AsyncSession):
    stripe_sub_id = session.get("subscription")
    customer_id = session.get("customer")
    email = (session.get("customer_details") or {}).get("email", "")
    referred_by = (session.get("metadata") or {}).get("referral_code", "") or None

    if not stripe_sub_id or not email:
        return

    try:
        stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
        period_start = datetime.fromtimestamp(stripe_sub["current_period_start"], tz=timezone.utc).replace(tzinfo=None)
        period_end = datetime.fromtimestamp(stripe_sub["current_period_end"], tz=timezone.utc).replace(tzinfo=None)
    except Exception:
        period_start = period_end = None

    referral_code = _generate_referral_code()

    sub = Subscription(
        stripe_subscription_id=stripe_sub_id,
        stripe_customer_id=customer_id or "",
        buyer_email=email.lower().strip(),
        status="active",
        plan="pro",
        leads_per_month=PLAN_LEADS,
        credits_remaining=PLAN_LEADS,
        rollover_credits=0,
        current_period_start=period_start,
        current_period_end=period_end,
        referral_code=referral_code,
        referred_by_code=referred_by if referred_by else None,
    )
    db.add(sub)

    # Apply referral bonus if a valid code was used
    if referred_by:
        referrer_result = await db.execute(
            select(Subscription).where(Subscription.referral_code == referred_by)
        )
        referrer = referrer_result.scalar_one_or_none()
        if referrer:
            sub.credits_remaining = min(PLAN_LEADS + REFERRAL_BONUS_CREDITS, PLAN_LEADS * 2)
            referrer.credits_remaining = min(
                referrer.credits_remaining + REFERRAL_BONUS_CREDITS,
                referrer.leads_per_month * 2,
            )
            logger.info(f"[referral] New subscriber {email} used code {referred_by} — both +{REFERRAL_BONUS_CREDITS} credits")

    await db.commit()

    # Send welcome email
    from app.services.subscriber_mailer import send_welcome
    await send_welcome(email.lower().strip(), db)

    logger.info(f"[subscription] New subscriber: {email}")


async def handle_invoice_paid(invoice: dict, db: AsyncSession):
    stripe_sub_id = invoice.get("subscription")
    if not stripe_sub_id:
        return

    billing_reason = invoice.get("billing_reason", "")
    if billing_reason == "subscription_create":
        return

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return

    # Roll over unused credits (cap at 1× monthly = up to 600 total)
    unused = sub.credits_remaining
    rollover = min(unused, sub.leads_per_month)

    try:
        stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
        sub.current_period_start = datetime.fromtimestamp(
            stripe_sub["current_period_start"], tz=timezone.utc
        ).replace(tzinfo=None)
        sub.current_period_end = datetime.fromtimestamp(
            stripe_sub["current_period_end"], tz=timezone.utc
        ).replace(tzinfo=None)
    except Exception:
        pass

    sub.credits_remaining = sub.leads_per_month
    sub.rollover_credits = rollover
    sub.status = "active"
    await db.commit()
    logger.info(f"[subscription] Credits reset for {sub.buyer_email} — rolled over {rollover} credits")


# ── Cancel ────────────────────────────────────────────────────────────────────

@router.post("/subscription/cancel")
async def cancel_subscription(
    email: str = Depends(require_session),
    db: AsyncSession = Depends(get_db),
):
    """Cancel at period end — subscriber keeps access until billing date."""
    sub = await _get_active_sub(email, db)
    if not sub:
        raise HTTPException(status_code=404, detail="No active subscription found.")
    try:
        stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=True)
        sub.status = "canceling"
        await db.commit()
        access_until = sub.current_period_end.isoformat() if sub.current_period_end else None
        logger.info(f"[subscription] {email} set to cancel at period end")
        return {"canceled": True, "access_until": access_until}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cancellation failed: {e}")


# ── List Business ─────────────────────────────────────────────────────────────

class BusinessListingRequest(BaseModel):
    business_name: str
    industry: str
    city: str
    state: str
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    contact_name: str | None = None
    full_address: str | None = None


@router.post("/list-business")
async def list_business(body: BusinessListingRequest, db: AsyncSession = Depends(get_db)):
    """Self-submit a business to be listed in the lead database."""
    from app.models import Lead
    from sqlalchemy import select as sa_select

    source_url = f"self:{body.business_name.strip().lower()}:{body.city.strip().lower()}:{body.state.strip().lower()}"
    existing = await db.execute(sa_select(Lead).where(Lead.source_url == source_url))
    if existing.scalar_one_or_none():
        return {"success": True, "already_listed": True}

    lead = Lead(
        business_name=body.business_name.strip(),
        industry=body.industry.strip(),
        city=body.city.strip(),
        state=body.state.strip().upper()[:2],
        phone=body.phone.strip() if body.phone else None,
        email=body.email.strip().lower() if body.email else None,
        website=body.website.strip() if body.website else None,
        contact_name=body.contact_name.strip() if body.contact_name else None,
        full_address=body.full_address.strip() if body.full_address else None,
        source_url=source_url,
        source="self_submitted",
        lead_type="business",
    )
    db.add(lead)
    await db.commit()
    logger.info(f"[listing] New self-submitted business: {body.business_name} ({body.industry}, {body.city}, {body.state})")
    return {"success": True, "already_listed": False}


async def handle_invoice_failed(invoice: dict, db: AsyncSession):
    stripe_sub_id = invoice.get("subscription")
    if not stripe_sub_id:
        return

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return

    logger.warning(f"[subscription] Payment failed for {sub.buyer_email}")

    if settings.resend_api_key:
        from app.services.email_sender import send_email
        next_attempt = invoice.get("next_payment_attempt")
        retry_str = ""
        if next_attempt:
            retry_date = datetime.fromtimestamp(next_attempt, tz=timezone.utc).strftime("%B %d")
            retry_str = f"Stripe will automatically retry on <strong>{retry_date}</strong>."
        html = f"""
<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;color:#1e293b;">
  <div style="background:#dc2626;padding:20px 28px;border-radius:12px 12px 0 0;">
    <span style="color:white;font-weight:900;font-size:20px;">Payment Failed</span>
  </div>
  <div style="background:#f8fafc;padding:32px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0;">
    <h2 style="margin-top:0;color:#1e293b;">We couldn&apos;t charge your card</h2>
    <p>Your LeadGen Pro subscription payment for <strong>{sub.buyer_email}</strong> failed.</p>
    <p>{retry_str}</p>
    <p>To avoid losing access, please update your payment method in Stripe:</p>
    <p style="margin:24px 0;">
      <a href="https://billing.stripe.com/p/login/test_00g00000000000"
         style="background:#2563eb;color:white;padding:14px 28px;text-decoration:none;
                border-radius:8px;font-weight:bold;font-size:15px;display:inline-block;">
        Update Payment Method →
      </a>
    </p>
    <p style="font-size:12px;color:#94a3b8;">
      Questions? Reply to this email or contact support@takeyourleadtoday.com
    </p>
  </div>
</div>"""
        await send_email(sub.buyer_email, "Action required: Payment failed", html)


async def handle_subscription_canceled(stripe_sub: dict, db: AsyncSession):
    stripe_sub_id = stripe_sub.get("id")
    if not stripe_sub_id:
        return

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.status = "canceled"
        sub.canceled_at = datetime.utcnow()
        await db.commit()
        logger.info(f"[subscription] Canceled: {sub.buyer_email}")
