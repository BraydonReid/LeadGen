"""
Email nurture sequence for free-sample downloaders.

Sequence (day 0 already handled by sample router):
  Stage 1 — Day 2:  "Why our phone data beats Apollo"
  Stage 2 — Day 5:  "How [industry] companies use lead lists"
  Stage 3 — Day 9:  "Your leads are aging — here's what's new"
  Stage 4 — Day 14: 10% off first purchase coupon

Runs every 6 hours via APScheduler. Sends at most one email per stage per recipient.
Respects nurture_unsubscribed flag (set when any email bounces or user opts out).
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import SampleRequest

logger = logging.getLogger(__name__)

# Days after sample download each stage fires
NURTURE_SCHEDULE = {
    1: 2,
    2: 5,
    3: 9,
    4: 14,
}

MAX_STAGE = max(NURTURE_SCHEDULE.keys())
BATCH_SIZE = 50


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _coupon_code() -> str:
    """Generate a short promo code for the Day-14 discount email."""
    return f"WELCOME10-{secrets.token_hex(3).upper()}"


def _stage1_html(industry: str, state: str, frontend_url: str) -> str:
    industry_title = industry.title()
    shop_url = f"{frontend_url}/shop?industry={industry}&state={state}"
    return f"""
<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;color:#1e293b;">
  <div style="background:#2563eb;padding:20px 28px;border-radius:12px 12px 0 0;">
    <span style="color:white;font-weight:900;font-size:20px;">Take Your Lead Today</span>
  </div>
  <div style="background:#f8fafc;padding:32px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0;">
    <h2 style="margin-top:0;color:#1e293b;">Why our phone data is 20–30% better than Apollo</h2>
    <p style="color:#475569;">Quick follow-up on your {industry_title} sample download.</p>
    <p style="color:#475569;">Most lead vendors (Apollo, ZoomInfo, D7) show phone coverage rates of
       60–75% for contractor data. We're at <strong>98% in Texas</strong>. Here's why that matters:</p>
    <ul style="color:#475569;line-height:1.8;">
      <li>Our scrapers run <strong>continuously</strong> — all data refreshed within 12 months</li>
      <li>We pull from Yelp, YellowPages, BBB, and city permit records simultaneously</li>
      <li>Competitors buy bulk data from aggregators — ours is scraped directly</li>
      <li>Dead numbers are caught during re-scraping and removed automatically</li>
    </ul>
    <p style="margin:28px 0;">
      <a href="{shop_url}"
         style="background:#2563eb;color:white;padding:14px 28px;text-decoration:none;
                border-radius:8px;font-weight:bold;font-size:15px;display:inline-block;">
        Browse {industry_title} Leads →
      </a>
    </p>
    <p style="font-size:12px;color:#94a3b8;">
      Take Your Lead Today &bull;
      <a href="{frontend_url}/unsubscribe-nurture?email={{email}}" style="color:#94a3b8;">Unsubscribe</a>
    </p>
  </div>
</div>"""


def _stage2_html(industry: str, state: str, frontend_url: str) -> str:
    industry_title = industry.title()
    shop_url = f"{frontend_url}/shop?industry={industry}&state={state}"
    intent_url = f"{frontend_url}/intent-leads"
    return f"""
<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;color:#1e293b;">
  <div style="background:#2563eb;padding:20px 28px;border-radius:12px 12px 0 0;">
    <span style="color:white;font-weight:900;font-size:20px;">Take Your Lead Today</span>
  </div>
  <div style="background:#f8fafc;padding:32px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0;">
    <h2 style="margin-top:0;color:#1e293b;">3 ways companies use {industry_title} lead lists</h2>
    <p style="color:#475569;">How our customers get the most out of their download:</p>
    <ol style="color:#475569;line-height:2;">
      <li><strong>Cold calling campaigns</strong> — sort by conversion score, call the top 20% first</li>
      <li><strong>Direct mail</strong> — use the full address to send postcards to high-score leads</li>
      <li><strong>Referral outreach</strong> — contact contractors in adjacent industries for referral partnerships</li>
    </ol>
    <p style="color:#475569;">Pro tip: our <strong>consumer intent leads</strong> (from building permits and code violations)
       convert at 5–15× the rate of cold directory leads because the homeowner has an active, urgent need.</p>
    <p style="margin:28px 0;">
      <a href="{intent_url}"
         style="background:#f97316;color:white;padding:14px 28px;text-decoration:none;
                border-radius:8px;font-weight:bold;font-size:15px;display:inline-block;">
        See Consumer Intent Leads →
      </a>
    </p>
    <p style="margin-top:16px;">
      <a href="{shop_url}"
         style="color:#2563eb;font-size:14px;text-decoration:none;font-weight:600;">
        Or browse standard {industry_title} leads →
      </a>
    </p>
    <p style="font-size:12px;color:#94a3b8;margin-top:32px;">
      Take Your Lead Today &bull;
      <a href="{frontend_url}/unsubscribe-nurture?email={{email}}" style="color:#94a3b8;">Unsubscribe</a>
    </p>
  </div>
</div>"""


def _stage3_html(industry: str, state: str, frontend_url: str) -> str:
    industry_title = industry.title()
    shop_url = f"{frontend_url}/shop?industry={industry}&state={state}"
    return f"""
<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;color:#1e293b;">
  <div style="background:#2563eb;padding:20px 28px;border-radius:12px 12px 0 0;">
    <span style="color:white;font-weight:900;font-size:20px;">Take Your Lead Today</span>
  </div>
  <div style="background:#f8fafc;padding:32px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0;">
    <h2 style="margin-top:0;color:#1e293b;">Your sample leads are 9 days old — here's what's new</h2>
    <p style="color:#475569;">Since you downloaded your {industry_title} sample, our scrapers have added
       hundreds of new leads in {state}.</p>
    <p style="color:#475569;">Unlike Apollo or ZoomInfo, we don't sell you a static snapshot from a
       year ago. Our database is scraped <strong>continuously</strong> — new businesses are added daily,
       and businesses that close naturally age out.</p>
    <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:16px;margin:20px 0;">
      <div style="font-weight:700;color:#1e40af;margin-bottom:6px;">What's different about our freshness:</div>
      <ul style="color:#1e40af;margin:0;padding-left:18px;font-size:14px;line-height:1.8;">
        <li>All leads scraped within 12 months (most within 30 days)</li>
        <li>Businesses that close are removed at re-scrape time</li>
        <li>Phone numbers re-validated each scrape cycle</li>
        <li>No year-old contact lists sold as "current"</li>
      </ul>
    </div>
    <p style="margin:28px 0;">
      <a href="{shop_url}"
         style="background:#2563eb;color:white;padding:14px 28px;text-decoration:none;
                border-radius:8px;font-weight:bold;font-size:15px;display:inline-block;">
        Browse New {industry_title} Leads →
      </a>
    </p>
    <p style="font-size:12px;color:#94a3b8;margin-top:32px;">
      Take Your Lead Today &bull;
      <a href="{frontend_url}/unsubscribe-nurture?email={{email}}" style="color:#94a3b8;">Unsubscribe</a>
    </p>
  </div>
</div>"""


def _stage4_html(industry: str, state: str, frontend_url: str, coupon: str) -> str:
    industry_title = industry.title()
    shop_url = f"{frontend_url}/shop?industry={industry}&state={state}&coupon={coupon}"
    return f"""
<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;color:#1e293b;">
  <div style="background:#2563eb;padding:20px 28px;border-radius:12px 12px 0 0;">
    <span style="color:white;font-weight:900;font-size:20px;">Take Your Lead Today</span>
  </div>
  <div style="background:#f8fafc;padding:32px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0;">
    <h2 style="margin-top:0;color:#1e293b;">10% off your first {industry_title} order</h2>
    <p style="color:#475569;">You downloaded a free sample two weeks ago. We'd love to earn your business.</p>
    <div style="background:#f0fdf4;border:2px dashed #22c55e;border-radius:8px;padding:20px;
                text-align:center;margin:20px 0;">
      <div style="font-size:13px;color:#15803d;font-weight:600;text-transform:uppercase;
                  letter-spacing:0.05em;margin-bottom:6px;">Your discount code</div>
      <div style="font-size:28px;font-weight:900;color:#15803d;letter-spacing:0.1em;">{coupon}</div>
      <div style="font-size:12px;color:#4ade80;margin-top:6px;">10% off — one-time use</div>
    </div>
    <p style="color:#475569;font-size:14px;">Apply at checkout. Valid for any {industry_title} lead order.</p>
    <p style="margin:28px 0;">
      <a href="{shop_url}"
         style="background:#16a34a;color:white;padding:14px 28px;text-decoration:none;
                border-radius:8px;font-weight:bold;font-size:15px;display:inline-block;">
        Claim 10% Off {industry_title} Leads →
      </a>
    </p>
    <p style="color:#94a3b8;font-size:13px;">
      No expiry. No minimum order. Pay only for what you download.
    </p>
    <p style="font-size:12px;color:#94a3b8;margin-top:32px;">
      Take Your Lead Today &bull;
      <a href="{frontend_url}/unsubscribe-nurture?email={{email}}" style="color:#94a3b8;">Unsubscribe</a>
    </p>
  </div>
</div>"""


_STAGE_SUBJECTS = {
    1: "Why our phone data is 20–30% better (quick note)",
    2: "3 ways companies use {industry} lead lists",
    3: "Your {industry} sample is 9 days old — here's what's new",
    4: "10% off your first {industry} order",
}


async def run_nurture_batch(db: AsyncSession) -> int:
    """
    Send the next nurture email for all sample requests that are due.
    Returns the number of emails sent.
    """
    if not settings.smtp_password:
        return 0

    from app.services.email_sender import send_email

    now = _now()
    sent_count = 0

    # Find sample requests that need their next nurture email
    stmt = (
        select(SampleRequest)
        .where(
            SampleRequest.nurture_stage < MAX_STAGE,
            SampleRequest.nurture_unsubscribed == False,  # noqa: E712
        )
        .order_by(SampleRequest.created_at.asc())
        .limit(BATCH_SIZE)
    )
    result = await db.execute(stmt)
    samples = result.scalars().all()

    for sample in samples:
        next_stage = sample.nurture_stage + 1
        days_required = NURTURE_SCHEDULE[next_stage]
        send_after = sample.created_at + timedelta(days=days_required)

        if now < send_after:
            continue  # not due yet

        industry = sample.industry
        state = sample.state
        frontend_url = settings.frontend_url
        email = sample.email

        if next_stage == 1:
            html = _stage1_html(industry, state, frontend_url).replace("{email}", email)
            subject = _STAGE_SUBJECTS[1]
        elif next_stage == 2:
            html = _stage2_html(industry, state, frontend_url).replace("{email}", email)
            subject = _STAGE_SUBJECTS[2].format(industry=industry.title())
        elif next_stage == 3:
            html = _stage3_html(industry, state, frontend_url).replace("{email}", email)
            subject = _STAGE_SUBJECTS[3].format(industry=industry.title())
        elif next_stage == 4:
            coupon = _coupon_code()
            html = _stage4_html(industry, state, frontend_url, coupon).replace("{email}", email)
            subject = _STAGE_SUBJECTS[4].format(industry=industry.title())
        else:
            continue

        try:
            await send_email(email, subject, html)
            sample.nurture_stage = next_stage
            sample.nurture_last_sent_at = now
            sent_count += 1
            logger.info(f"[nurture] Stage {next_stage} sent to {email} ({industry}/{state})")
        except Exception as e:
            logger.warning(f"[nurture] Failed to send stage {next_stage} to {email}: {e}")

    if sent_count > 0:
        await db.commit()

    return sent_count
