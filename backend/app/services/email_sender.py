"""
Resend email sender.

Sends cold outreach emails via the Resend API (https://resend.com).
All emails are CAN-SPAM compliant: unsubscribe link, physical address, from name.

Template tokens (replaced at send time):
  {business_name}   - the lead's business name
  {industry}        - industry (e.g. "roofing")
  {city}            - city (e.g. "Dallas")
  {lead_count}      - number of leads available for their industry+city
  {sample_url}      - link to claim free leads
  {unsubscribe_url} - one-click unsubscribe link (required by CAN-SPAM)
"""
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

RESEND_API = "https://api.resend.com/emails"

# CAN-SPAM footer — included in every email
CAN_SPAM_FOOTER = """
<div style="margin-top:40px;padding-top:20px;border-top:1px solid #eee;
            font-size:11px;color:#999;font-family:Arial,sans-serif;">
  <p>You're receiving this because your business appears in public directories.
     <a href="{unsubscribe_url}" style="color:#999;">Unsubscribe</a></p>
  <p>LeadGen &bull; Texas, USA</p>
</div>
"""

# Default outreach template — personalized per lead
DEFAULT_SUBJECT = "I have {lead_count} {industry} leads in {city} — want 10 free?"

DEFAULT_BODY_HTML = """
<div style="font-family:Arial,sans-serif;max-width:600px;color:#333;">
  <p>Hi {business_name},</p>

  <p>I run a lead generation platform focused on Texas contractors and I noticed your
  {industry} business in {city}.</p>

  <p>Right now I have <strong>{lead_count} verified {industry} leads in {city}</strong> —
  homeowners and businesses actively looking for contractors. These include people who've
  recently pulled building permits (meaning they're <em>actively in the market right now</em>),
  plus businesses sourced from public directories with verified phone numbers.</p>

  <p>I'd like to send you <strong>10 leads completely free</strong> so you can see the
  quality before spending anything.</p>

  <p style="margin:30px 0;">
    <a href="{sample_url}"
       style="background:#2563eb;color:white;padding:12px 24px;
              text-decoration:none;border-radius:6px;font-weight:bold;">
      Claim Your 10 Free Leads →
    </a>
  </p>

  <p>No credit card. No commitment. If the leads are useful, I sell packages starting
  at just $0.50/lead.</p>

  <p>Best,<br>The LeadGen Team</p>

  {can_spam_footer}
</div>
"""

# Follow-up template (sequence step 2)
FOLLOWUP_SUBJECT = "Following up — free {industry} leads in {city}"

FOLLOWUP_BODY_HTML = """
<div style="font-family:Arial,sans-serif;max-width:600px;color:#333;">
  <p>Hi {business_name},</p>

  <p>Just following up on my note from a few days ago about free {industry} leads
  in {city}.</p>

  <p>The offer is still open — <strong>10 leads free, no strings attached</strong>.
  I just want to show you what we have before you decide.</p>

  <p style="margin:30px 0;">
    <a href="{sample_url}"
       style="background:#2563eb;color:white;padding:12px 24px;
              text-decoration:none;border-radius:6px;font-weight:bold;">
      Get My Free Leads →
    </a>
  </p>

  <p>Best,<br>The LeadGen Team</p>

  {can_spam_footer}
</div>
"""

# Final follow-up (sequence step 3)
FINAL_SUBJECT = "Last chance — {lead_count} {industry} leads in {city}"

FINAL_BODY_HTML = """
<div style="font-family:Arial,sans-serif;max-width:600px;color:#333;">
  <p>Hi {business_name},</p>

  <p>Last note — I'm closing out my outreach list for {city} {industry} contractors
  and wanted to make sure you didn't miss the free sample offer.</p>

  <p>If you ever want leads in your area, visit us at
  <a href="{site_url}">{site_url}</a>.</p>

  <p>Best,<br>The LeadGen Team</p>

  {can_spam_footer}
</div>
"""

STEP_SUBJECTS = {1: DEFAULT_SUBJECT, 2: FOLLOWUP_SUBJECT, 3: FINAL_SUBJECT}
STEP_BODIES = {1: DEFAULT_BODY_HTML, 2: FOLLOWUP_BODY_HTML, 3: FINAL_BODY_HTML}


def render_template(template: str, **kwargs) -> str:
    can_spam = CAN_SPAM_FOOTER.format(**kwargs)
    return template.format(can_spam_footer=can_spam, site_url=settings.site_url, **kwargs)


async def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    reply_to: str | None = None,
) -> str | None:
    """
    Send a single email via Resend. Returns the message ID on success, None on failure.
    """
    if not settings.resend_api_key:
        logger.warning("[email] RESEND_API_KEY not set — email not sent")
        return None

    payload = {
        "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }
    if reply_to:
        payload["reply_to"] = reply_to

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                RESEND_API,
                json=payload,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            )
            if resp.status_code == 200:
                return resp.json().get("id")
            logger.warning(f"[email] Resend error {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"[email] Send failed to {to_email}: {e}")
    return None
