import csv
import io
from typing import Generator

from app.models import Lead


def generate_csv(leads: list[Lead]) -> Generator[str, None, None]:
    """Stream CSV rows as strings."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "business_name", "contact_name", "contact_title", "city", "state", "zip_code",
        "full_address", "email", "phone", "website", "linkedin_url",
        "lead_type", "quality_score", "ai_conversion_score",
        "yelp_rating", "review_count", "years_in_business", "date_added",
    ])
    yield output.getvalue()
    output.truncate(0)
    output.seek(0)

    for lead in leads:
        scraped = getattr(lead, "scraped_date", None)
        writer.writerow([
            lead.business_name,
            getattr(lead, "contact_name", "") or "",
            getattr(lead, "contact_title", "") or "",
            lead.city,
            lead.state,
            getattr(lead, "zip_code", "") or "",
            getattr(lead, "full_address", "") or "",
            lead.email or "",
            lead.phone or "",
            lead.website or "",
            getattr(lead, "linkedin_url", "") or "",
            getattr(lead, "lead_type", "business") or "business",
            getattr(lead, "quality_score", "") if getattr(lead, "quality_score", None) is not None else "",
            getattr(lead, "conversion_score", "") if getattr(lead, "conversion_score", None) is not None else "",
            getattr(lead, "yelp_rating", "") if getattr(lead, "yelp_rating", None) is not None else "",
            getattr(lead, "review_count", "") if getattr(lead, "review_count", None) is not None else "",
            getattr(lead, "years_in_business", "") if getattr(lead, "years_in_business", None) is not None else "",
            scraped.strftime("%Y-%m-%d") if scraped else "",
        ])
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)
