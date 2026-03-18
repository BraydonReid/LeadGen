import csv
import io
from typing import Generator

from app.models import Lead


def generate_csv(leads: list[Lead]) -> Generator[str, None, None]:
    """Stream CSV rows as strings."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "business_name", "contact_name", "city", "state", "zip_code",
        "full_address", "email", "phone", "website",
        "lead_type", "quality_score",
    ])
    yield output.getvalue()
    output.truncate(0)
    output.seek(0)

    for lead in leads:
        writer.writerow([
            lead.business_name,
            getattr(lead, "contact_name", "") or "",
            lead.city,
            lead.state,
            getattr(lead, "zip_code", "") or "",
            getattr(lead, "full_address", "") or "",
            lead.email or "",
            lead.phone or "",
            lead.website or "",
            getattr(lead, "lead_type", "business") or "business",
            getattr(lead, "quality_score", "") if getattr(lead, "quality_score", None) is not None else "",
        ])
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)
