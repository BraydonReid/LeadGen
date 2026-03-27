"""
Subscriber lifecycle email system.

Sends automated emails to subscribers at key moments:
  - welcome        : immediately on subscription creation
  - tips_day3      : day 3, if they haven't downloaded yet (how to use AI scores)
  - checkin_day7   : day 7, ask if they closed any jobs (social proof request)
  - low_credits    : when credits drop below 20% of monthly allowance
  - expiry_warning : 5 days before period ends with credits remaining
  - weekly_digest  : every Monday with new lead counts in top industries

Uses Resend (already configured). Tracks sent emails in subscriber_emails_sent
to prevent duplicate sends across scheduler runs.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Lead, Subscription, SubscriberEmailSent, SubscriptionDownload
from app.services.email_sender import send_email

logger = logging.getLogger(__name__)

FRONTEND_URL = settings.site_url or "https://takeyourleadtoday.com"


# ── Email templates ────────────────────────────────────────────────────────────

def _base(body: str) -> str:
    return f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1e293b;">
  <div style="background:#2563eb;padding:20px 28px;border-radius:12px 12px 0 0;">
    <span style="color:white;font-weight:900;font-size:20px;">Take Your Lead Today</span>
  </div>
  <div style="background:#f8fafc;padding:28px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0;">
    {body}
    <div style="margin-top:32px;padding-top:20px;border-top:1px solid #e2e8f0;font-size:11px;color:#94a3b8;">
      <p>You're receiving this because you have an active Take Your Lead Today subscription.</p>
      <p>Manage your subscription at <a href="{FRONTEND_URL}/my-subscription" style="color:#2563eb;">{FRONTEND_URL}/my-subscription</a></p>
    </div>
  </div>
</div>"""


WELCOME_SUBJECT = "Welcome to Take Your Lead Today Pro — here's how to get your first leads"
WELCOME_BODY = _base("""
  <h2 style="color:#1e293b;margin-top:0;">You're in. Let's get you some leads.</h2>
  <p>Your Pro subscription is active. You have <strong>300 credits</strong> to spend this month —
  each credit = one verified business lead in CSV format.</p>

  <h3 style="color:#2563eb;">Get your first leads in 3 steps:</h3>
  <ol style="line-height:1.8;">
    <li>Go to <a href="{portal_url}" style="color:#2563eb;">your subscriber portal</a></li>
    <li>Choose an industry (e.g. Roofing) + state (e.g. TX) + quantity</li>
    <li>Hit Download — your CSV arrives instantly</li>
  </ol>

  <p style="margin:24px 0;">
    <a href="{portal_url}"
       style="background:#2563eb;color:white;padding:12px 24px;text-decoration:none;
              border-radius:8px;font-weight:bold;display:inline-block;">
      Download Your First Leads →
    </a>
  </p>

  <p><strong>Pro tip:</strong> Filter by AI conversion score — leads scored 70+ have the
  highest predicted close rate. These are the ones to call first.</p>

  <p>Questions? Just reply to this email.</p>
  <p>— The Take Your Lead Today Team</p>
""")


TIPS_DAY3_SUBJECT = "Your 300 leads are waiting — quick tip to find the best ones first"
TIPS_DAY3_BODY = _base("""
  <h2 style="color:#1e293b;margin-top:0;">Make the most of your credits</h2>
  <p>We noticed you haven't downloaded your first batch yet — no rush, but here's
  how to find the highest-quality leads when you're ready:</p>

  <h3 style="color:#2563eb;">Use AI Conversion Scores</h3>
  <p>Every lead in our database gets scored 0–100 by our AI model based on:
  website quality, contact richness, business signals, and market data.</p>
  <ul style="line-height:1.8;">
    <li><strong>70–100:</strong> High-intent businesses — call these first</li>
    <li><strong>40–69:</strong> Good prospects with solid potential</li>
    <li><strong>0–39:</strong> Basic leads — useful for volume outreach</li>
  </ul>

  <p style="margin:24px 0;">
    <a href="{portal_url}"
       style="background:#2563eb;color:white;padding:12px 24px;text-decoration:none;
              border-radius:8px;font-weight:bold;display:inline-block;">
      Get My Leads →
    </a>
  </p>
  <p>— The Take Your Lead Today Team</p>
""")


CHECKIN_DAY7_SUBJECT = "Quick check-in — did you close any jobs from your leads?"
CHECKIN_DAY7_BODY = _base("""
  <h2 style="color:#1e293b;margin-top:0;">How's it going?</h2>
  <p>It's been a week since you joined Take Your Lead Today Pro. We'd love to hear how
  your outreach is going.</p>

  <p>If you closed even one job from our leads, we'd really appreciate a quick
  testimonial — it helps other contractors trust the platform and helps us
  keep improving data quality for you.</p>

  <p>Just reply to this email with a sentence or two about your experience.
  No pressure — even "haven't started yet" is helpful feedback.</p>

  <p style="margin:24px 0;">
    <a href="{portal_url}"
       style="background:#2563eb;color:white;padding:12px 24px;text-decoration:none;
              border-radius:8px;font-weight:bold;display:inline-block;">
      Download More Leads →
    </a>
  </p>
  <p>— The Take Your Lead Today Team</p>
""")


LOW_CREDITS_SUBJECT = "You're running low on credits this month ({credits_remaining} left)"
LOW_CREDITS_BODY = _base("""
  <h2 style="color:#1e293b;margin-top:0;">Use your remaining credits before they reset</h2>
  <p>You have <strong>{credits_remaining} lead credits left</strong> this month.
  Your subscription resets on <strong>{period_end}</strong>.</p>
  <p>Unused credits <strong>roll over</strong> (up to one extra month), so nothing
  goes to waste — but now's a great time to grab a fresh batch while you're thinking about it.</p>

  <p style="margin:24px 0;">
    <a href="{portal_url}"
       style="background:#2563eb;color:white;padding:12px 24px;text-decoration:none;
              border-radius:8px;font-weight:bold;display:inline-block;">
      Download {credits_remaining} More Leads →
    </a>
  </p>
  <p>— The Take Your Lead Today Team</p>
""")


EXPIRY_WARNING_SUBJECT = "Your {credits_remaining} unused credits roll over in 5 days"
EXPIRY_WARNING_BODY = _base("""
  <h2 style="color:#1e293b;margin-top:0;">Your month resets on {period_end}</h2>
  <p>You have <strong>{credits_remaining} credits remaining</strong>.
  They'll roll over to next month automatically (up to 300 bonus credits).</p>
  <p>Want to use some before the reset? Download a fresh batch now:</p>

  <p style="margin:24px 0;">
    <a href="{portal_url}"
       style="background:#2563eb;color:white;padding:12px 24px;text-decoration:none;
              border-radius:8px;font-weight:bold;display:inline-block;">
      Download Leads Now →
    </a>
  </p>
  <p>— The Take Your Lead Today Team</p>
""")


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _already_sent(email: str, email_type: str, db: AsyncSession) -> bool:
    result = await db.execute(
        select(SubscriberEmailSent)
        .where(SubscriberEmailSent.email == email.lower())
        .where(SubscriberEmailSent.email_type == email_type)
    )
    return result.scalar_one_or_none() is not None


async def _mark_sent(email: str, email_type: str, db: AsyncSession) -> None:
    db.add(SubscriberEmailSent(email=email.lower(), email_type=email_type))
    await db.commit()


def _fmt_date(dt: datetime | None) -> str:
    if not dt:
        return "your next billing date"
    return dt.strftime("%B %d")


# ── Per-event senders ──────────────────────────────────────────────────────────

async def send_welcome(email: str, db: AsyncSession) -> bool:
    if await _already_sent(email, "welcome", db):
        return False
    body = WELCOME_BODY.format(portal_url=f"{FRONTEND_URL}/my-subscription")
    msg_id = await send_email(email, WELCOME_SUBJECT, body)
    if msg_id:
        await _mark_sent(email, "welcome", db)
        logger.info(f"[mailer] Welcome sent → {email}")
    return bool(msg_id)


async def send_tips_day3(email: str, db: AsyncSession) -> bool:
    if await _already_sent(email, "tips_day3", db):
        return False
    body = TIPS_DAY3_BODY.format(portal_url=f"{FRONTEND_URL}/my-subscription")
    msg_id = await send_email(email, TIPS_DAY3_SUBJECT, body)
    if msg_id:
        await _mark_sent(email, "tips_day3", db)
    return bool(msg_id)


async def send_checkin_day7(email: str, db: AsyncSession) -> bool:
    if await _already_sent(email, "checkin_day7", db):
        return False
    body = CHECKIN_DAY7_BODY.format(portal_url=f"{FRONTEND_URL}/my-subscription")
    msg_id = await send_email(email, CHECKIN_DAY7_SUBJECT, body)
    if msg_id:
        await _mark_sent(email, "checkin_day7", db)
    return bool(msg_id)


async def send_low_credits(
    email: str, credits_remaining: int, period_end: datetime | None, db: AsyncSession
) -> bool:
    # Only send once per billing period — use a type key that includes the month
    period_key = f"low_credits_{_fmt_date(period_end)}"
    if await _already_sent(email, period_key, db):
        return False
    body = LOW_CREDITS_BODY.format(
        credits_remaining=credits_remaining,
        period_end=_fmt_date(period_end),
        portal_url=f"{FRONTEND_URL}/my-subscription",
    )
    subject = LOW_CREDITS_SUBJECT.format(credits_remaining=credits_remaining)
    msg_id = await send_email(email, subject, body)
    if msg_id:
        await _mark_sent(email, period_key, db)
    return bool(msg_id)


async def send_expiry_warning(
    email: str, credits_remaining: int, period_end: datetime | None, db: AsyncSession
) -> bool:
    period_key = f"expiry_warning_{_fmt_date(period_end)}"
    if await _already_sent(email, period_key, db):
        return False
    body = EXPIRY_WARNING_BODY.format(
        credits_remaining=credits_remaining,
        period_end=_fmt_date(period_end),
        portal_url=f"{FRONTEND_URL}/my-subscription",
    )
    subject = EXPIRY_WARNING_SUBJECT.format(credits_remaining=credits_remaining)
    msg_id = await send_email(email, subject, body)
    if msg_id:
        await _mark_sent(email, period_key, db)
    return bool(msg_id)


async def send_weekly_digest(email: str, db: AsyncSession) -> bool:
    """
    Monday morning digest: top 3 industries with the most new leads added this week.
    Uses period key 'weekly_YYYY_WXX' to send at most once per calendar week.
    """
    now = datetime.utcnow()
    week_key = f"weekly_{now.strftime('%Y_W%U')}"
    if await _already_sent(email, week_key, db):
        return False

    cutoff = now - timedelta(days=7)
    rows = (await db.execute(
        select(Lead.industry, func.count().label("cnt"))
        .where(
            Lead.scraped_date >= cutoff,
            Lead.duplicate_of_id.is_(None),
            Lead.lead_type == "business",
        )
        .group_by(Lead.industry)
        .order_by(func.count().desc())
        .limit(3)
    )).all()

    if not rows:
        return False

    portal_url = f"{FRONTEND_URL}/my-subscription"
    industry_rows = "".join(
        f"""<tr>
              <td style="padding:10px 0;border-bottom:1px solid #e2e8f0;">
                <strong>{r.industry.title()}</strong>
              </td>
              <td style="padding:10px 0;border-bottom:1px solid #e2e8f0;text-align:right;color:#2563eb;font-weight:bold;">
                +{r.cnt:,} new leads
              </td>
            </tr>"""
        for r in rows
    )
    total_new = sum(r.cnt for r in rows)
    top_industry = rows[0].industry.title()
    subject = f"{total_new:,} new leads added this week — {top_industry} leads + more"

    body = _base(f"""
  <h2 style="color:#1e293b;margin-top:0;">Fresh leads added this week</h2>
  <p>Here's what was added to the database in the last 7 days:</p>
  <table style="width:100%;border-collapse:collapse;">
    {industry_rows}
  </table>
  <p style="margin-top:16px;color:#64748b;font-size:13px;">
    All leads are sorted by AI conversion score so you always get the best ones first.
  </p>
  <p style="margin:24px 0;">
    <a href="{portal_url}"
       style="background:#2563eb;color:white;padding:12px 24px;text-decoration:none;
              border-radius:8px;font-weight:bold;display:inline-block;">
      Download This Week's Leads →
    </a>
  </p>
  <p>— The Take Your Lead Today Team</p>
""")

    msg_id = await send_email(email, subject, body)
    if msg_id:
        await _mark_sent(email, week_key, db)
        logger.info(f"[mailer] Weekly digest sent → {email} ({total_new} new leads)")
    return bool(msg_id)


# ── Main scheduler job ─────────────────────────────────────────────────────────

async def run_subscriber_email_job(db: AsyncSession) -> dict:
    """
    Called every hour by the scheduler. Checks all active subscribers and
    sends appropriate lifecycle emails. Safe to call repeatedly.
    """
    if not settings.smtp_password:
        return {"skipped": "RESEND_API_KEY not configured"}

    now = datetime.utcnow()
    result = await db.execute(
        select(Subscription).where(Subscription.status == "active")
    )
    subs = result.scalars().all()

    sent = {"welcome": 0, "tips_day3": 0, "checkin_day7": 0,
            "low_credits": 0, "expiry_warning": 0, "weekly_digest": 0}
    is_monday = now.weekday() == 0

    for sub in subs:
        email = sub.buyer_email
        age_days = (now - sub.created_at).days if sub.created_at else 0
        credits_pct = (sub.credits_remaining / sub.leads_per_month * 100) if sub.leads_per_month else 100

        # Welcome — same day
        if age_days == 0:
            if await send_welcome(email, db):
                sent["welcome"] += 1

        # Day 3 tips — only if they haven't downloaded anything yet
        elif age_days >= 3:
            has_download = (await db.execute(
                select(SubscriptionDownload)
                .where(SubscriptionDownload.subscription_id == sub.id)
                .limit(1)
            )).scalar_one_or_none()
            if not has_download:
                if await send_tips_day3(email, db):
                    sent["tips_day3"] += 1

        # Day 7 check-in
        if age_days >= 7:
            if await send_checkin_day7(email, db):
                sent["checkin_day7"] += 1

        # Low credits warning — below 20%
        if credits_pct < 20 and sub.credits_remaining > 0:
            if await send_low_credits(email, sub.credits_remaining, sub.current_period_end, db):
                sent["low_credits"] += 1

        # Expiry warning — 5 days before period end, if credits remain
        if sub.current_period_end and sub.credits_remaining > 0:
            days_until_reset = (sub.current_period_end - now).days
            if 4 <= days_until_reset <= 6:
                if await send_expiry_warning(email, sub.credits_remaining, sub.current_period_end, db):
                    sent["expiry_warning"] += 1

        # Weekly digest — every Monday, shows top industries with new leads
        if is_monday and age_days >= 7:
            if await send_weekly_digest(email, db):
                sent["weekly_digest"] += 1

    total = sum(sent.values())
    if total:
        logger.info(f"[mailer] Subscriber emails sent: {sent}")
    return sent
