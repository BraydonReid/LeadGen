from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ScrapedLead:
    business_name: str
    industry: str
    city: str
    state: str
    website: str | None = None
    email: str | None = None
    phone: str | None = None
    source_url: str | None = None
    zip_code: str | None = None
    full_address: str | None = None
    contact_name: str | None = None
    source: str = "yellowpages"
    lead_type: str = "business"
    # Quality/reputation signals — populated by API sources that provide them
    yelp_rating: float | None = None      # 0.0–5.0 star rating
    review_count: int | None = None       # total number of reviews
    years_in_business: int | None = None  # calculated from founding year


class BaseScraper(ABC):
    @abstractmethod
    def scrape(self, industry: str, city: str, state: str, max_results: int = 100) -> list[ScrapedLead]:
        """Scrape leads for a given industry + location."""
        ...
