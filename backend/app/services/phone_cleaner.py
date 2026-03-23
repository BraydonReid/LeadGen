"""
Phone number normalization and validation.

Normalizes US phone numbers to (XXX) XXX-XXXX format and validates:
- Must be 10 digits after stripping non-digits
- Area code cannot be 000, 911, 411
- Cannot be all the same digit (e.g. 5555555555)
- Strips +1 country code if present

Runs as a background batch job on existing leads.
"""
import re
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead

logger = logging.getLogger(__name__)

# Area codes that don't exist or are reserved
_INVALID_AREA_CODES = {"000", "911", "411", "555"}


def normalize_phone(raw: str | None) -> tuple[str | None, bool]:
    """
    Returns (normalized_phone, is_valid).
    normalized_phone is None if invalid.
    """
    if not raw:
        return None, False

    digits = re.sub(r"\D", "", raw)

    # Strip leading country code +1
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) != 10:
        return None, False

    area = digits[:3]
    exchange = digits[3:6]

    # Reject reserved area codes
    if area in _INVALID_AREA_CODES:
        return None, False

    # Reject all-same-digit numbers (1111111111, 0000000000, etc.)
    if len(set(digits)) == 1:
        return None, False

    # Reject obviously fake exchanges (555-0100 through 555-0199 are fiction numbers)
    if area == "555" and exchange.startswith("01"):
        return None, False

    # Reject area code starting with 0 or 1 (not valid in NANP)
    if area[0] in ("0", "1"):
        return None, False

    normalized = f"({area}) {exchange}-{digits[6:]}"
    return normalized, True


async def clean_phones_batch(db: AsyncSession, batch_size: int = 2000) -> dict:
    """
    Normalize and validate phone numbers for leads not yet processed.
    Returns {"processed": N, "valid": N, "invalid": N}
    """
    stmt = (
        select(Lead)
        .where(Lead.phone.isnot(None))
        .where(Lead.phone_valid.is_(None))
        .limit(batch_size)
    )
    result = await db.execute(stmt)
    leads = result.scalars().all()

    if not leads:
        return {"processed": 0, "valid": 0, "invalid": 0}

    valid_count = 0
    invalid_count = 0

    for lead in leads:
        normalized, is_valid = normalize_phone(lead.phone)
        lead.phone_valid = is_valid
        if is_valid and normalized:
            lead.phone = normalized
            valid_count += 1
        else:
            invalid_count += 1

    await db.commit()
    logger.info(f"[phone_cleaner] Processed {len(leads)}: {valid_count} valid, {invalid_count} invalid")
    return {"processed": len(leads), "valid": valid_count, "invalid": invalid_count}


async def clean_phones_remaining(db: AsyncSession) -> int:
    """Returns count of leads with phones not yet validated."""
    from sqlalchemy import func, select
    result = await db.execute(
        select(func.count()).select_from(Lead)
        .where(Lead.phone.isnot(None))
        .where(Lead.phone_valid.is_(None))
    )
    return result.scalar_one()
