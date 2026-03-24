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

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.ehlo()
        server.starttls()
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
