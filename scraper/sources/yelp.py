"""
Yelp Places API (v3) scraper.

Requires a free Yelp API key:
  1. Go to https://www.yelp.com/developers/v3/manage_apps
  2. Create an app → copy the API Key → add to .env: YELP_API_KEY=...

Budget tracking and call gating is handled in main.py via yelp_budget.py.
This class just makes the API calls and returns leads + how many calls were used.

Differentiator vs Apollo/ZoomInfo: captures yelp_rating + review_count.
"""

import os
import time

import httpx

from sources.base import BaseScraper, ScrapedLead

YELP_API_BASE = "https://api.yelp.com/v3"


class YelpScraper(BaseScraper):
    def __init__(self):
        self.api_key = os.environ.get("YELP_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("YELP_API_KEY not set")

    def scrape(self, industry: str, city: str, state: str, max_results: int = 100) -> list[ScrapedLead]:
        """Standard BaseScraper interface — returns leads list only."""
        leads, _ = self.scrape_with_count(industry, city, state, max_results)
        return leads

    def scrape_with_count(self, industry: str, city: str, state: str, max_results: int = 100) -> tuple[list[ScrapedLead], int]:
        """Returns (leads, api_calls_made) so caller can track budget."""
        leads = []
        location = f"{city}, {state}"
        offset = 0
        per_page = 50  # always max — most value per API call
        calls_made = 0

        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

        with httpx.Client(headers=headers, timeout=15) as client:
            while len(leads) < max_results:
                params = {
                    "term": industry,
                    "location": location,
                    "limit": per_page,
                    "offset": offset,
                    "sort_by": "review_count",  # most-reviewed = best quality leads
                }
                try:
                    resp = client.get(f"{YELP_API_BASE}/businesses/search", params=params)
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    print(f"[yelp-api] HTTP error: {e}")
                    break

                calls_made += 1
                data = resp.json()
                businesses = data.get("businesses", [])
                if not businesses:
                    break

                for biz in businesses:
                    lead = self._parse_business(biz, industry, state)
                    if lead:
                        leads.append(lead)

                offset += per_page
                if offset >= 1000 or offset >= data.get("total", 0):
                    break
                time.sleep(0.5)

        return leads[:max_results], calls_made

    def _parse_business(self, biz: dict, industry: str, state: str) -> ScrapedLead | None:
        business_name = biz.get("name", "").strip()
        if not business_name or biz.get("is_closed", False):
            return None

        location = biz.get("location", {})
        city = location.get("city", "").strip()
        biz_state = location.get("state", state).strip().upper()
        zip_code = location.get("zip_code", "").strip() or None
        display_address = location.get("display_address", [])
        full_address = ", ".join(display_address) if display_address else None

        raw_phone = biz.get("phone", "")
        phone = raw_phone.replace("+1", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        if len(phone) != 10:
            phone = None

        yelp_url = biz.get("url", "").split("?")[0] or None

        return ScrapedLead(
            business_name=business_name,
            industry=industry.lower(),
            city=city,
            state=biz_state,
            website=None,
            phone=phone,
            zip_code=zip_code,
            full_address=full_address,
            source_url=yelp_url,
            source="yelp",
            yelp_rating=biz.get("rating"),
            review_count=biz.get("review_count"),
        )
