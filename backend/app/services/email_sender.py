"""
SMTP email sender — works with Gmail, GoDaddy, or any SMTP provider.

Gmail setup:
  1. Enable 2-Step Verification on your Google account
  2. Go to myaccount.google.com → Security → App Passwords
  3. Generate an App Password for "Mail"
  4. Set SMTP_USER=you@gmail.com and SMTP_PASSWORD=<16-char app password> in .env
"""
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)

# ── Email templates (used by email_campaigns router) ──────────────────────────

CAN_SPAM_FOOTER = """
<div style="margin-top:40px;padding-top:20px;border-top:1px solid #eee;
            font-size:11px;color:#999;font-family:Arial,sans-serif;">
  <p>You're receiving this because your business appears in public directories.
     <a href="{unsubscribe_url}" style="color:#999;">Unsubscribe</a></p>
  <p>Take Your Lead Today &bull; Texas, USA</p>
</div>
"""

DEFAULT_SUBJECT = "I have {lead_count} {industry} leads in {city} — want 5 free?"
DEFAULT_BODY_HTML = """
<div style="font-family:Arial,sans-serif;max-width:600px;color:#333;">
  <p>Hi {business_name},</p>
  <p>I run a lead generation platform and I noticed your {industry} business in {city}.</p>
  <p>Right now I have <strong>{lead_count} verified {industry} leads in {city}</strong> —
  businesses actively looking for contractors.</p>
  <p>I'd like to send you <strong>5 leads completely free</strong> so you can see the quality.</p>
  <p style="margin:30px 0;">
    <a href="{sample_url}" style="background:#2563eb;color:white;padding:12px 24px;
       text-decoration:none;border-radius:6px;font-weight:bold;">
      Claim Your 5 Free Leads →
    </a>
  </p>
  <p>Best,<br>The Take Your Lead Today Team</p>
  {can_spam_footer}
</div>
"""

FOLLOWUP_SUBJECT = "Following up — free {industry} leads in {city}"
FOLLOWUP_BODY_HTML = """
<div style="font-family:Arial,sans-serif;max-width:600px;color:#333;">
  <p>Hi {business_name},</p>
  <p>Just following up — the offer for <strong>5 free {industry} leads in {city}</strong> is still open.</p>
  <p style="margin:30px 0;">
    <a href="{sample_url}" style="background:#2563eb;color:white;padding:12px 24px;
       text-decoration:none;border-radius:6px;font-weight:bold;">
      Get My Free Leads →
    </a>
  </p>
  <p>Best,<br>The Take Your Lead Today Team</p>
  {can_spam_footer}
</div>
"""

FINAL_SUBJECT = "Last chance — {lead_count} {industry} leads in {city}"
FINAL_BODY_HTML = """
<div style="font-family:Arial,sans-serif;max-width:600px;color:#333;">
  <p>Hi {business_name},</p>
  <p>Last note — if you ever want leads in your area, visit
  <a href="{site_url}">{site_url}</a>.</p>
  <p>Best,<br>The Take Your Lead Today Team</p>
  {can_spam_footer}
</div>
"""

STEP_SUBJECTS = {1: DEFAULT_SUBJECT, 2: FOLLOWUP_SUBJECT, 3: FINAL_SUBJECT}
STEP_BODIES   = {1: DEFAULT_BODY_HTML, 2: FOLLOWUP_BODY_HTML, 3: FINAL_BODY_HTML}


def render_template(template: str, **kwargs) -> str:
    can_spam = CAN_SPAM_FOOTER.format(**kwargs)
    return template.format(can_spam_footer=can_spam, site_url=settings.site_url, **kwargs)


# ── SMTP sender ────────────────────────────────────────────────────────────────

def _send_sync(to_email: str, subject: str, html_body: str, reply_to: str | None = None):
    """Synchronous SMTP send — called via asyncio.to_thread."""
    from_addr = settings.email_from_address or settings.smtp_user
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.email_from_name} <{from_addr}>"
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.attach(MIMEText(html_body, "html"))

    # Port 465 = SSL/TLS (GoDaddy default), port 587 = STARTTLS
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as server:
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(from_addr, to_email, msg.as_string())
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()  # required again after STARTTLS
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(from_addr, to_email, msg.as_string())


async def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    reply_to: str | None = None,
) -> bool:
    """Send an email via SMTP. Returns True on success."""
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("[email] SMTP_USER/SMTP_PASSWORD not set — email not sent")
        return False
    try:
        await asyncio.to_thread(_send_sync, to_email, subject, html_body, reply_to)
        logger.info(f"[email] Sent '{subject}' to {to_email}")
        return True
    except Exception as e:
        logger.error(f"[email] Failed to send to {to_email}: {e}")
        return False
