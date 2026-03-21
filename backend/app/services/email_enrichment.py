"""
Email enrichment background job.

For leads that have a website but no email address, queries Hunter.io to find
a contact email. When an email is found:
  1. Updates the lead record with the email + source/timestamp
  2. Resets ai_scored_at/conversion_score to NULL so the AI scorer re-processes
     the lead with the richer data (email boosts conversion score significantly)

Runs on a schedule from APScheduler. Skips gracefully if Hunter key not set.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead
from app.services.hunter import find_email_for_lead

logger = logging.getLogger(__name__)

BATCH_SIZE = 50  # Hunter free tier is 25/month; paid tiers handle more


async def enrich_leads_batch(db: AsyncSession, batch_size: int = BATCH_SIZE) -> int:
    """
    Find emails for leads that have a website but no email.
    Skips leads already attempted in the last 30 days.
    Returns the number of emails successfully found and saved.
    """
    from app.config import settings
    if not settings.hunter_api_key:
        return 0

    # Select leads: have website, missing email, not recently attempted
    stmt = (
        select(Lead)
        .where(Lead.website.isnot(None))
        .where(Lead.email.is_(None))
        .where(Lead.enrichment_attempted_at.is_(None))
        .order_by(Lead.scraped_date.desc())   # newest leads first — most likely to be active
        .limit(batch_size)
    )
    result = await db.execute(stmt)
    leads = result.scalars().all()

    if not leads:
        return 0

    found = 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for lead in leads:
        email = await find_email_for_lead(lead.website)

        if email:
            # Update email + mark source — reset AI scoring so it gets re-scored with email signal
            await db.execute(
                update(Lead)
                .where(Lead.id == lead.id)
                .values(
                    email=email,
                    email_source="hunter",
                    email_found_at=now,
                    enrichment_attempted_at=now,
                    # Reset AI scoring — email is a strong conversion signal, worth re-scoring
                    ai_scored_at=None,
                    conversion_score=None,
                )
            )
            found += 1
            logger.info(f"[enrichment] Found email for lead {lead.id} ({lead.business_name}): {email}")
        else:
            # Mark attempted so we don't retry this lead every run
            await db.execute(
                update(Lead)
                .where(Lead.id == lead.id)
                .values(enrichment_attempted_at=now)
            )

    await db.commit()
    logger.info(f"[enrichment] Processed {len(leads)} leads, found {found} emails")
    return found
