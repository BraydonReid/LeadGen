"""
Background AI conversion scoring service.

Processes unscored leads in batches using a local Ollama LLM.
Scores reflect conversion likelihood — not just data completeness.
Called by APScheduler every 30 minutes; also triggerable via /api/internal/score-leads.
"""
import asyncio
import json
import logging

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import openai

from app.models import Lead
from app.services.openai_client import generate

logger = logging.getLogger(__name__)

SCORING_PROMPT = """\
You are a lead quality analyst for a B2B lead generation company.

Score the following business lead for CONVERSION LIKELIHOOD — the probability that a sales rep \
contacting this business will result in a qualified conversation or sale. Score 0-100.

Lead profile:
- Business: {business_name}
- Industry: {industry}
- Location: {city}, {state}
- Has Phone: {has_phone}
- Has Email: {has_email}
- Has Website: {has_website}
- Has Street Address: {has_address}
- Has Named Contact: {has_contact}
- Website URL: {website}

Scoring guide:
- 85-100: Multiple contact methods, named contact, established web presence, high-value industry
- 65-84: Good contact data, appears active, reachable business
- 45-64: Partial data, reachable but may require extra effort
- 25-44: Minimal data, cold outreach will be difficult
- 0-24: Very limited data, likely outdated or very hard to reach

Respond ONLY with a valid JSON object and nothing else:
{{"conversion_score": <int 0-100>, "website_quality": <int 0-100>, "contact_richness": <int 0-100>, "reasoning": "<one sentence>"}}"""


def _build_prompt(lead: Lead) -> str:
    return SCORING_PROMPT.format(
        business_name=lead.business_name,
        industry=lead.industry,
        city=lead.city,
        state=lead.state,
        has_phone="Yes" if lead.phone else "No",
        has_email="Yes" if lead.email else "No",
        has_website="Yes" if lead.website else "No",
        has_address="Yes" if lead.full_address else "No",
        has_contact="Yes" if lead.contact_name else "No",
        website=lead.website or "None",
    )


def _parse_response(response: str) -> dict:
    """Extract JSON from LLM response, handling preamble text."""
    start = response.find("{")
    end = response.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON found in response: {response[:200]}")
    return json.loads(response[start:end])


async def score_lead_batch(db: AsyncSession, batch_size: int = 50) -> int:
    """
    Score the oldest unscored leads. Processes newest leads first (highest revenue value).
    Returns the number of leads successfully scored.
    """
    stmt = (
        select(Lead)
        .where(Lead.ai_scored_at.is_(None))
        .order_by(Lead.scraped_date.desc())
        .limit(batch_size)
    )
    result = await db.execute(stmt)
    leads = result.scalars().all()

    if not leads:
        return 0

    # Score up to 5 leads concurrently (respects 500 RPM / 200k TPM limits)
    sem = asyncio.Semaphore(5)

    async def _score_one(lead: Lead) -> dict | None:
        async with sem:
            try:
                prompt = _build_prompt(lead)
                response = await generate(prompt, temperature=0.1)
                return {"id": lead.id, **_parse_response(response)}
            except openai.RateLimitError:
                # Limit hit — leave unscored so scheduler retries later
                logger.warning(f"[ai_scoring] Rate limited on lead {lead.id}, skipping")
                return None
            except Exception as e:
                logger.warning(f"[ai_scoring] Failed lead {lead.id}: {e}")
                return {"id": lead.id, "conversion_score": 50}

    results = await asyncio.gather(*[_score_one(lead) for lead in leads])

    scored = 0
    for data in results:
        if data is None:
            continue
        await db.execute(
            update(Lead)
            .where(Lead.id == data["id"])
            .values(
                conversion_score=min(100, max(0, int(data["conversion_score"]))),
                website_quality_signal=min(100, max(0, int(data.get("website_quality", 50)))),
                contact_richness_signal=min(100, max(0, int(data.get("contact_richness", 50)))),
                ai_scored_at=func.now(),
            )
        )
        scored += 1

    await db.commit()
    logger.info(f"[ai_scoring] Scored {scored}/{len(leads)} leads in this batch")
    return scored
