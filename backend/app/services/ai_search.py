"""
AI natural language search service.

Parses free-text queries like "small roofing companies in Texas without websites"
into structured database filters using a local Ollama LLM.
"""
import json
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Lead
from app.schemas import AISearchIntent, AISearchResponse, PricedLeadPreview, SearchQuery
from app.services.ollama_client import generate
from app.services.pricing import calculate_lead_price

logger = logging.getLogger(__name__)

PARSE_PROMPT = """\
You are a search intent parser for a B2B lead generation marketplace.
Parse the user's natural language query into structured database filters.

Known industries: roofing, plumbing, hvac, solar, electrician, landscaping, pest control, \
remodeling, flooring, painting, cleaning, handyman, tree service, pool service, moving, \
auto repair, dentist, chiropractor, insurance, law firm, real estate, medical, accountant, \
financial advisor, mortgage, construction, siding, windows, gutters, concrete, fencing, \
pressure washing, drywall, insulation, garage door, security, it support, photography, \
catering, veterinarian, dog grooming, carpet cleaning, mold remediation.

US state codes (2-letter): AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD \
MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY

User query: "{query}"

Rules:
- Extract the most specific industry that matches. If unclear, set null.
- Extract state code if a US state is mentioned. City is optional.
- has_website=false means "without a website" or "no website". has_website=true means "with a website".
- quality_filter="high" for "good quality", "established", "high quality". quality_filter="low" for "small", "new", "basic".
- sort_by="conversion_score" is the default. Use "freshness" only if user mentions "recent" or "new". Use "quality_score" for "complete data".
- lead_type="consumer" only if user says "homeowners" or "service requests". Default null.

Respond ONLY with a valid JSON object and nothing else:
{{"industry": <string or null>, "state": <2-letter string or null>, "city": <string or null>, \
"lead_type": <"business"|"consumer"|null>, "has_website": <true|false|null>, \
"has_email": <true|false|null>, "has_phone": <true|false|null>, \
"quality_filter": <"high"|"low"|null>, "sort_by": <"conversion_score"|"quality_score"|"freshness">, \
"natural_explanation": "<one concise sentence summarizing what was understood>"}}"""


async def parse_search_intent(query: str) -> AISearchIntent:
    """Use LLM to extract structured intent from a natural language query."""
    prompt = PARSE_PROMPT.format(query=query)
    response = await generate(settings.ollama_search_model, prompt, temperature=0.0)

    # Robust JSON extraction — LLMs sometimes add surrounding text
    start = response.find("{")
    end = response.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON in LLM response: {response[:300]}")

    data = json.loads(response[start:end])
    return AISearchIntent(**data)


async def ai_search(db: AsyncSession, query: str, max_results: int = 50) -> AISearchResponse:
    """Parse natural language query and run structured database search."""
    intent = await parse_search_intent(query)

    filters = [Lead.times_sold < 5]

    if intent.industry:
        filters.append(func.lower(Lead.industry).contains(intent.industry.lower()))
    if intent.state:
        filters.append(Lead.state == intent.state.upper())
    if intent.city:
        filters.append(func.lower(Lead.city).contains(intent.city.lower()))
    if intent.lead_type:
        filters.append(Lead.lead_type == intent.lead_type)
    if intent.has_website is True:
        filters.append(Lead.website.isnot(None))
    if intent.has_website is False:
        filters.append(Lead.website.is_(None))
    if intent.has_email is True:
        filters.append(Lead.email.isnot(None))
    if intent.has_email is False:
        filters.append(Lead.email.is_(None))
    if intent.has_phone is True:
        filters.append(Lead.phone.isnot(None))
    if intent.quality_filter == "high":
        filters.append(Lead.quality_score >= 70)
    if intent.quality_filter == "low":
        filters.append(Lead.quality_score < 50)

    # Build order clause based on extracted intent
    sort_map = {
        "conversion_score": Lead.conversion_score.desc().nulls_last(),
        "quality_score": Lead.quality_score.desc().nulls_last(),
        "freshness": Lead.scraped_date.desc(),
    }
    order_col = sort_map.get(intent.sort_by or "conversion_score", Lead.conversion_score.desc().nulls_last())

    count_stmt = select(func.count()).select_from(Lead).where(*filters)
    total_count = (await db.execute(count_stmt)).scalar_one()

    # Fetch up to 100 leads for price calculation + 10-lead preview
    sample_stmt = select(Lead).where(*filters).order_by(order_col).limit(100)
    sample_leads = (await db.execute(sample_stmt)).scalars().all()

    prices = [calculate_lead_price(lead) for lead in sample_leads]
    avg_price = sum(prices) / len(prices) if prices else 0.0

    preview_leads = sample_leads[:10]
    preview = [
        PricedLeadPreview(
            id=lead.id,
            business_name=lead.business_name,
            industry=lead.industry,
            city=lead.city,
            state=lead.state,
            website=lead.website,
            phone=lead.phone,
            quality_score=lead.quality_score,
            conversion_score=lead.conversion_score,
            lead_type=lead.lead_type or "business",
            full_address=lead.full_address,
            yelp_rating=lead.yelp_rating,
            review_count=lead.review_count,
            years_in_business=lead.years_in_business,
            unit_price=prices[i],
        )
        for i, lead in enumerate(preview_leads)
    ]

    return AISearchResponse(
        intent=intent,
        total_count=total_count,
        avg_lead_price=round(avg_price, 4),
        preview=preview,
        query=SearchQuery(
            industry=intent.industry or "",
            state=intent.state or "",
            city=intent.city,
            lead_type=intent.lead_type,
        ),
    )
