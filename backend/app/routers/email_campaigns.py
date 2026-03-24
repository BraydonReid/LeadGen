"""
Email campaign management router.

Endpoints:
  POST /api/email/campaigns              — create a campaign
  GET  /api/email/campaigns              — list all campaigns with stats
  POST /api/email/campaigns/{id}/launch  — activate a campaign (starts sending)
  POST /api/email/campaigns/{id}/pause   — pause sending
  GET  /api/email/campaigns/{id}/stats   — open/click/reply rates
  GET  /api/email/track/open/{send_id}   — 1x1 pixel open tracker
  GET  /api/email/track/click/{send_id}  — click tracker (redirects to destination)
  GET  /api/email/unsubscribe/{token}    — one-click unsubscribe (CAN-SPAM required)
  POST /api/email/campaigns/send-pending — trigger sending pending emails (called by scheduler)
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import EmailCampaign, EmailSend, EmailUnsubscribe, Lead
from app.services.email_sender import (
    STEP_BODIES,
    STEP_SUBJECTS,
    render_template,
    send_email,
)

router = APIRouter()
logger = logging.getLogger(__name__)

TRACKING_PIXEL = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff"
    b"\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00"
    b"\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# ── Schemas ──────────────────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    name: str
    industry_filter: str | None = None
    state_filter: str | None = None
    city_filter: str | None = None
    template_subject: str | None = None   # uses default if omitted
    template_body_html: str | None = None  # uses default if omitted


class CampaignResponse(BaseModel):
    id: int
    name: str
    status: str
    industry_filter: str | None
    state_filter: str | None
    city_filter: str | None
    emails_sent: int
    emails_opened: int
    emails_clicked: int
    open_rate: float
    click_rate: float
    created_at: datetime

    class Config:
        from_attributes = True


# ── Helpers ──────────────────────────────────────────────────────────────────

def _unsubscribe_url(token: str, site_url: str) -> str:
    from app.config import settings
    base = site_url or settings.site_url
    return f"{base}/api/email/unsubscribe/{token}"


def _sample_url(industry: str, city: str, state: str, site_url: str) -> str:
    from app.config import settings
    base = site_url or settings.site_url
    ind = industry.lower().replace(" ", "-")
    return f"{base}/shop?industry={ind}&city={city}&state={state}&sample=1"


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/email/campaigns", response_model=CampaignResponse)
async def create_campaign(payload: CampaignCreate, db: AsyncSession = Depends(get_db)):
    from app.config import settings
    from app.services.email_sender import DEFAULT_SUBJECT, DEFAULT_BODY_HTML

    campaign = EmailCampaign(
        name=payload.name,
        status="draft",
        industry_filter=payload.industry_filter,
        state_filter=payload.state_filter,
        city_filter=payload.city_filter,
        template_subject=payload.template_subject or DEFAULT_SUBJECT,
        template_body_html=payload.template_body_html or DEFAULT_BODY_HTML,
        from_name=settings.email_from_name,
        from_email=settings.email_from_address or settings.smtp_user,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return _to_response(campaign)


@router.get("/email/campaigns", response_model=list[CampaignResponse])
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailCampaign).order_by(EmailCampaign.created_at.desc()))
    campaigns = result.scalars().all()
    return [_to_response(c) for c in campaigns]


@router.post("/email/campaigns/{campaign_id}/launch")
async def launch_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """
    Activate a campaign. On first launch, creates EmailSend records for every
    eligible lead (has email, not unsubscribed, matches filters).
    """
    result = await db.execute(select(EmailCampaign).where(EmailCampaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    # Build lead query from filters
    query = select(Lead).where(Lead.email.isnot(None))
    if campaign.industry_filter:
        query = query.where(Lead.industry == campaign.industry_filter)
    if campaign.state_filter:
        query = query.where(Lead.state == campaign.state_filter)
    if campaign.city_filter:
        query = query.where(func.lower(Lead.city) == campaign.city_filter.lower())

    leads_result = await db.execute(query)
    leads = leads_result.scalars().all()

    # Get global unsubscribe list
    unsub_result = await db.execute(select(EmailUnsubscribe.email))
    unsubscribed = {row[0].lower() for row in unsub_result.all()}

    # Skip leads already in this campaign
    existing_result = await db.execute(
        select(EmailSend.lead_id).where(EmailSend.campaign_id == campaign_id)
    )
    already_queued = {row[0] for row in existing_result.all()}

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    queued = 0
    for lead in leads:
        if lead.id in already_queued:
            continue
        if lead.email.lower() in unsubscribed:
            continue
        send = EmailSend(
            campaign_id=campaign_id,
            lead_id=lead.id,
            email=lead.email,
            sequence_step=1,
            next_send_at=now,   # ready to send immediately
            unsubscribe_token=secrets.token_urlsafe(32),
        )
        db.add(send)
        queued += 1

    await db.execute(
        update(EmailCampaign).where(EmailCampaign.id == campaign_id).values(status="active")
    )
    await db.commit()
    return {"status": "active", "queued": queued}


@router.post("/email/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(
        update(EmailCampaign).where(EmailCampaign.id == campaign_id).values(status="paused")
    )
    await db.commit()
    return {"status": "paused"}


@router.get("/email/campaigns/{campaign_id}/stats")
async def campaign_stats(campaign_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailCampaign).where(EmailCampaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return _to_response(campaign)


@router.post("/email/campaigns/send-pending")
async def send_pending(db: AsyncSession = Depends(get_db)):
    """
    Called by APScheduler every 15 minutes. Sends emails that are due.
    Handles all 3 sequence steps.
    """
    from app.config import settings
    if not settings.smtp_password:
        return {"sent": 0, "reason": "RESEND_API_KEY not configured"}

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Find pending sends from active campaigns
    stmt = (
        select(EmailSend, EmailCampaign, Lead)
        .join(EmailCampaign, EmailSend.campaign_id == EmailCampaign.id)
        .join(Lead, EmailSend.lead_id == Lead.id)
        .where(EmailCampaign.status == "active")
        .where(EmailSend.sent_at.is_(None))
        .where(EmailSend.next_send_at <= now)
        .where(EmailSend.unsubscribed_at.is_(None))
        .limit(100)   # cap per scheduler run to avoid burst
    )
    result = await db.execute(stmt)
    rows = result.all()

    # Get unsubscribe list once
    unsub_result = await db.execute(select(EmailUnsubscribe.email))
    unsubscribed = {row[0].lower() for row in unsub_result.all()}

    # Get lead counts for personalization (industry × city)
    count_cache: dict[tuple, int] = {}

    sent_count = 0
    for send, campaign, lead in rows:
        if lead.email.lower() in unsubscribed:
            await db.execute(
                update(EmailSend).where(EmailSend.id == send.id)
                .values(unsubscribed_at=now)
            )
            continue

        # Get lead count for this industry+city (cached)
        cache_key = (lead.industry, lead.city, lead.state)
        if cache_key not in count_cache:
            cnt_result = await db.execute(
                select(func.count(Lead.id))
                .where(Lead.industry == lead.industry)
                .where(Lead.city == lead.city)
                .where(Lead.state == lead.state)
            )
            count_cache[cache_key] = cnt_result.scalar() or 0

        lead_count = count_cache[cache_key]
        unsub_url = _unsubscribe_url(send.unsubscribe_token, settings.site_url)
        sample_url = _sample_url(lead.industry, lead.city, lead.state, settings.site_url)

        step = send.sequence_step
        subject_tpl = campaign.template_subject if step == 1 else STEP_SUBJECTS.get(step, STEP_SUBJECTS[3])
        body_tpl = campaign.template_body_html if step == 1 else STEP_BODIES.get(step, STEP_BODIES[3])

        subject = subject_tpl.format(
            business_name=lead.business_name,
            industry=lead.industry,
            city=lead.city,
            lead_count=lead_count,
        )
        html_body = render_template(
            body_tpl,
            business_name=lead.business_name,
            industry=lead.industry,
            city=lead.city,
            lead_count=lead_count,
            sample_url=sample_url,
            unsubscribe_url=unsub_url,
        )

        message_id = await send_email(lead.email, subject, html_body)

        sequence_days = [int(d) for d in campaign.sequence_days.split(",")]
        next_step = step + 1
        next_send = None
        if next_step <= len(sequence_days):
            gap = sequence_days[next_step - 1] if next_step - 1 < len(sequence_days) else 0
            next_send = now + timedelta(days=gap) if gap > 0 else None

        await db.execute(
            update(EmailSend).where(EmailSend.id == send.id).values(
                sent_at=now,
                sequence_step=next_step,
                next_send_at=next_send,
                resend_message_id=message_id,
            )
        )
        await db.execute(
            update(EmailCampaign).where(EmailCampaign.id == campaign.id)
            .values(emails_sent=EmailCampaign.emails_sent + 1)
        )
        sent_count += 1

    await db.commit()
    logger.info(f"[campaigns] Sent {sent_count} emails")
    return {"sent": sent_count}


# ── Tracking endpoints ────────────────────────────────────────────────────────

@router.get("/email/track/open/{send_id}")
async def track_open(send_id: int, db: AsyncSession = Depends(get_db)):
    """1×1 transparent GIF — records email open."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    result = await db.execute(select(EmailSend).where(EmailSend.id == send_id))
    send = result.scalar_one_or_none()
    if send and not send.opened_at:
        await db.execute(
            update(EmailSend).where(EmailSend.id == send_id).values(opened_at=now)
        )
        await db.execute(
            update(EmailCampaign).where(EmailCampaign.id == send.campaign_id)
            .values(emails_opened=EmailCampaign.emails_opened + 1)
        )
        await db.commit()
    return Response(content=TRACKING_PIXEL, media_type="image/gif")


@router.get("/email/track/click/{send_id}")
async def track_click(send_id: int, url: str, db: AsyncSession = Depends(get_db)):
    """Records click and redirects to destination URL."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    result = await db.execute(select(EmailSend).where(EmailSend.id == send_id))
    send = result.scalar_one_or_none()
    if send and not send.clicked_at:
        await db.execute(
            update(EmailSend).where(EmailSend.id == send_id).values(clicked_at=now)
        )
        await db.execute(
            update(EmailCampaign).where(EmailCampaign.id == send.campaign_id)
            .values(emails_clicked=EmailCampaign.emails_clicked + 1)
        )
        await db.commit()
    return RedirectResponse(url=url)


@router.get("/email/unsubscribe/{token}")
async def unsubscribe(token: str, db: AsyncSession = Depends(get_db)):
    """One-click unsubscribe — CAN-SPAM required."""
    result = await db.execute(
        select(EmailSend).where(EmailSend.unsubscribe_token == token)
    )
    send = result.scalar_one_or_none()
    if not send:
        return HTMLResponse("<p>Unsubscribe link not found.</p>", status_code=404)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.execute(
        update(EmailSend).where(EmailSend.unsubscribe_token == token)
        .values(unsubscribed_at=now)
    )

    # Add to global unsubscribe list
    existing = await db.execute(
        select(EmailUnsubscribe).where(EmailUnsubscribe.email == send.email)
    )
    if not existing.scalar_one_or_none():
        db.add(EmailUnsubscribe(email=send.email))

    await db.commit()
    return HTMLResponse(
        "<html><body style='font-family:Arial;text-align:center;padding:60px'>"
        "<h2>You've been unsubscribed.</h2>"
        "<p>You won't receive any more emails from us.</p>"
        "</body></html>"
    )


# ── Helper ────────────────────────────────────────────────────────────────────

def _to_response(c: EmailCampaign) -> CampaignResponse:
    open_rate = round(c.emails_opened / c.emails_sent, 3) if c.emails_sent else 0.0
    click_rate = round(c.emails_clicked / c.emails_sent, 3) if c.emails_sent else 0.0
    return CampaignResponse(
        id=c.id, name=c.name, status=c.status,
        industry_filter=c.industry_filter, state_filter=c.state_filter,
        city_filter=c.city_filter, emails_sent=c.emails_sent,
        emails_opened=c.emails_opened, emails_clicked=c.emails_clicked,
        open_rate=open_rate, click_rate=click_rate, created_at=c.created_at,
    )
