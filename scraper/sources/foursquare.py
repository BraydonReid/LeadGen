"""
Foursquare Places API v3 scraper.

Requires a free Foursquare API key (no credit card):
  1. Go to https://foursquare.com/developers/
  2. Create an account and a new project
  3. Copy the API key and add to .env:
     FOURSQUARE_API_KEY=your_key_here

Free tier: 950 requests/day. Each request returns up to 50 places.
That's ~47,500 leads/day for free.

Returns: business name, address, phone, website, category, hours
Foursquare has excellent US coverage, especially for service businesses.
"""

import os
import time

import httpx

from sources.base import BaseScraper, ScrapedLead

FSQ_BASE = "https://api.foursquare.com/v3/places"

# Foursquare category IDs for home services / B2B targets
# https://docs.foursquare.com/data-products/docs/categories
FSQ_CATEGORY_MAP = {
    "roofing": "13064",        # Home Services
    "plumbing": "13064",
    "hvac": "13064",
    "electrician": "13064",
    "landscaping": "13064",
    "pest control": "13064",
    "cleaning": "13064",
    "auto repair": "11025",    # Automotive
    "dentist": "15014",        # Dental Office
    "medical": "15000",        # Healthcare
    "real estate": "11100",    # Real Estate
    "attorney": "11020",       # Legal
    "insurance": "11050",      # Insurance
    "accountant": "11001",     # Accounting
}


class FoursquareScraper(BaseScraper):
    def __init__(self):
        self.api_key = os.environ.get("FOURSQUARE_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "FOURSQUARE_API_KEY is not set. Get a free key at https://foursquare.com/developers/"
            )

    def scrape(self, industry: str, city: str, state: str, max_results: int = 100) -> list[ScrapedLead]:
        leads = []
        near = f"{city}, {state}"

        headers = {
            "Authorization": self.api_key,
            "Accept": "application/json",
        }

        cursor = None
        with httpx.Client(headers=headers, timeout=15) as client:
            while len(leads) < max_results:
                params = {
                    "query": industry,
                    "near": near,
                    "limit": min(50, max_results - len(leads)),
                    "fields": "name,location,tel,website,rating,stats,hours,fsq_id",
                }
                if cursor:
                    params["cursor"] = cursor

                try:
                    resp = client.get(f"{FSQ_BASE}/search", params=params)
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    print(f"[foursquare] HTTP error: {e}")
                    break

                data = resp.json()
                results = data.get("results", [])
                if not results:
                    break

                for place in results:
                    lead = self._parse_place(place, industry, state)
                    if lead:
                        leads.append(lead)

                # Pagination cursor
                cursor = data.get("context", {}).get("geo_bounds", {})
                # Foursquare doesn't use a simple cursor in v3 search — stop after one page
                break

        return leads[:max_results]

    def _parse_place(self, place: dict, industry: str, state: str) -> ScrapedLead | None:
        business_name = place.get("name", "").strip()
        if not business_name:
            return None

        location = place.get("location", {})
        city = location.get("locality", "").strip()
        biz_state = location.get("region", state).strip().upper()
        if len(biz_state) > 2:
            # Foursquare sometimes returns full state name — take first 2 chars as fallback
            biz_state = state.upper()
        zip_code = location.get("postcode", "").strip() or None

        # Build full address
        address_parts = []
        if location.get("address"):
            address_parts.append(location["address"])
        if city:
            address_parts.append(city)
        if biz_state:
            address_parts.append(biz_state)
        if zip_code:
            address_parts.append(zip_code)
        full_address = ", ".join(address_parts) if address_parts else None

        # Phone — Foursquare returns digits only, e.g. "5125551234"
        raw_phone = place.get("tel", "").replace("+1", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "").strip()
        phone = raw_phone if len(raw_phone) == 10 else None

        website = place.get("website", "").strip() or None
        # Strip UTM params
        if website and "?" in website:
            website = website.split("?")[0]

        fsq_id = place.get("fsq_id", "")
        source_url = f"https://foursquare.com/v/{fsq_id}" if fsq_id else None

        # Foursquare rating is 0–10, convert to 0–5
        raw_rating = place.get("rating")
        yelp_rating = round(raw_rating / 2.0, 1) if raw_rating else None

        stats = place.get("stats", {})
        review_count = stats.get("total_ratings") or stats.get("total_tips") or None

        if not city:
            return None

        return ScrapedLead(
            business_name=business_name,
            industry=industry.lower(),
            city=city,
            state=biz_state,
            website=website,
            phone=phone,
            zip_code=zip_code,
            full_address=full_address,
            source_url=source_url,
            source="foursquare",
            yelp_rating=yelp_rating,
            review_count=review_count,
        )
