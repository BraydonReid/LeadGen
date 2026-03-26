from pydantic import BaseModel


class LeadPreview(BaseModel):
    id: int
    business_name: str
    industry: str
    city: str
    state: str
    website: str | None
    phone: str | None
    quality_score: int | None = None
    conversion_score: int | None = None
    lead_type: str = "business"
    full_address: str | None = None
    # Reputation signals — differentiator vs Apollo/ZoomInfo
    yelp_rating: float | None = None
    review_count: int | None = None
    years_in_business: int | None = None

    class Config:
        from_attributes = True


class PricedLeadPreview(LeadPreview):
    unit_price: float


class SearchQuery(BaseModel):
    industry: str
    state: str
    city: str | None
    lead_type: str | None = None
    zip_code: str | None = None
    radius_miles: float | None = None
    # Advanced filters
    has_yelp: bool | None = None
    yelp_min: float | None = None
    yelp_max: float | None = None
    added_days: int | None = None
    min_quality: int | None = None
    has_email: bool | None = None
    has_contact: bool | None = None
    has_address: bool | None = None
    min_conversion: int | None = None


class SearchResponse(BaseModel):
    total_count: int
    preview: list[LeadPreview]
    query: SearchQuery


class ShopResponse(BaseModel):
    total_count: int
    avg_lead_price: float
    preview: list[PricedLeadPreview]
    query: SearchQuery


class IndustryStat(BaseModel):
    industry: str
    count: int


class StatsResponse(BaseModel):
    total_leads: int
    consumer_intent_count: int = 0
    industries: list[IndustryStat]
    pct_with_phone: float = 0.0
    pct_with_email: float = 0.0
    pct_ai_scored: float = 0.0
    pct_with_address: float = 0.0


class CheckoutRequest(BaseModel):
    industry: str
    state: str
    city: str | None = None
    quantity: int
    lead_type: str | None = None
    zip_code: str | None = None
    radius_miles: float | None = None
    promo_code: str | None = None
    # Ad attribution — passed from frontend UTM params
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    referrer: str | None = None


class CheckoutResponse(BaseModel):
    checkout_url: str
    total: float
    discount_pct: int
    avg_lead_price: float


class LeadReportRequest(BaseModel):
    session_id: str
    reason: str | None = None


class LeadReportResponse(BaseModel):
    credit_code: str
    discount_amount_dollars: float


class SampleRequestSchema(BaseModel):
    email: str
    industry: str
    state: str | None = None
    city: str | None = None
    lead_type: str | None = None
    zip_code: str | None = None
    radius_miles: float | None = None


class AISearchRequest(BaseModel):
    query: str
    max_results: int = 50


class AISearchIntent(BaseModel):
    industry: str | None = None
    state: str | None = None
    city: str | None = None
    lead_type: str | None = None
    has_website: bool | None = None
    has_email: bool | None = None
    has_phone: bool | None = None
    quality_filter: str | None = None
    sort_by: str = "conversion_score"
    natural_explanation: str = ""


class AISearchResponse(BaseModel):
    intent: AISearchIntent
    total_count: int
    avg_lead_price: float
    preview: list[PricedLeadPreview]
    query: SearchQuery


class ServiceRequestCreate(BaseModel):
    full_name: str
    email: str
    phone: str
    zip_code: str
    city: str
    state: str
    service_needed: str
    project_description: str | None = None
    timeline: str
    property_type: str


class ServiceRequestResponse(BaseModel):
    success: bool
    message: str
