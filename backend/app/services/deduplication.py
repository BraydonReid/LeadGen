"""
Lead deduplication service.

Finds duplicate leads by:
  1. Exact phone number match (same normalized phone, different source_url)
  2. Exact (business_name, city, state) match

When duplicates are found, keeps the record with the most data fields filled in
and marks the others with duplicate_of_id pointing to the canonical record.
Duplicate leads are excluded from shop search, downloads, and pricing.

Run via POST /api/internal/dedup-leads or the scheduler.
"""
import logging

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead

logger = logging.getLogger(__name__)


def _completeness_score(lead: Lead) -> int:
    """Score data completeness — higher means this record should be kept."""
    score = 0
    if lead.phone and lead.phone_valid:        score += 4
    if lead.email:                             score += 5
    if lead.website:                           score += 3
    if lead.full_address:                      score += 2
    if lead.contact_name:                      score += 2
    if lead.yelp_rating:                       score += 3
    if lead.review_count and lead.review_count > 0: score += 2
    if lead.zip_code:                          score += 1
    if lead.conversion_score is not None:      score += 2
    if lead.quality_score and lead.quality_score > 50: score += 1
    return score


async def deduplicate_by_phone(db: AsyncSession, batch_size: int = 200) -> int:
    """
    Find leads sharing the same normalized phone number.
    Keeps the most complete record; marks others as duplicates.
    """
    # Raw SQL: find phone numbers appearing more than once among non-duplicate leads
    dupes_stmt = text("""
        SELECT phone, array_agg(id ORDER BY scraped_date ASC) AS ids
        FROM leads
        WHERE phone IS NOT NULL
          AND phone_valid = true
          AND duplicate_of_id IS NULL
        GROUP BY phone
        HAVING count(*) > 1
        LIMIT :limit
    """)
    result = await db.execute(dupes_stmt, {"limit": batch_size})
    groups = result.fetchall()

    marked = 0
    for row in groups:
        phone, ids = row[0], row[1]
        leads_result = await db.execute(select(Lead).where(Lead.id.in_(ids)))
        leads = leads_result.scalars().all()

        leads_sorted = sorted(leads, key=_completeness_score, reverse=True)
        canonical = leads_sorted[0]

        for dupe in leads_sorted[1:]:
            if dupe.duplicate_of_id is None:
                dupe.duplicate_of_id = canonical.id
                marked += 1

    if marked:
        await db.commit()
        logger.info(f"[dedup] Phone dedup: marked {marked} duplicates")

    return marked


async def deduplicate_by_name_city(db: AsyncSession, batch_size: int = 200) -> int:
    """
    Find leads sharing the same (business_name, city, state) — case-insensitive.
    Keeps the most complete; marks others.
    """
    dupes_stmt = text("""
        SELECT lower(trim(business_name)) AS name_key,
               lower(trim(city)) AS city_key,
               lower(trim(state)) AS state_key,
               array_agg(id ORDER BY scraped_date ASC) AS ids
        FROM leads
        WHERE duplicate_of_id IS NULL
        GROUP BY name_key, city_key, state_key
        HAVING count(*) > 1
        LIMIT :limit
    """)
    result = await db.execute(dupes_stmt, {"limit": batch_size})
    groups = result.fetchall()

    marked = 0
    for row in groups:
        ids = row[3]
        leads_result = await db.execute(select(Lead).where(Lead.id.in_(ids)))
        leads = leads_result.scalars().all()

        leads_sorted = sorted(leads, key=_completeness_score, reverse=True)
        canonical = leads_sorted[0]

        for dupe in leads_sorted[1:]:
            if dupe.duplicate_of_id is None:
                dupe.duplicate_of_id = canonical.id
                marked += 1

    if marked:
        await db.commit()
        logger.info(f"[dedup] Name+city dedup: marked {marked} duplicates")

    return marked


async def run_dedup_pass(db: AsyncSession, batch_size: int = 200) -> dict:
    """Run both dedup strategies in one pass."""
    phone_dupes = await deduplicate_by_phone(db, batch_size)
    name_dupes = await deduplicate_by_name_city(db, batch_size)
    total = phone_dupes + name_dupes

    # Count total duplicates in DB
    total_dupes = (await db.execute(
        select(func.count()).select_from(Lead).where(Lead.duplicate_of_id.isnot(None))
    )).scalar_one()

    return {
        "marked_this_run": total,
        "phone_duplicates": phone_dupes,
        "name_city_duplicates": name_dupes,
        "total_duplicates_in_db": total_dupes,
    }
