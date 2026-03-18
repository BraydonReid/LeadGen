"""
Lead pricing engine.

Calculates per-lead price based on industry, data quality,
location, freshness, demand, and resale count.
"""

from datetime import datetime, timezone

INDUSTRY_BASE_PRICE: dict[str, float] = {
    "solar": 0.60,
    "roofing": 0.55,
    "hvac": 0.50,
    "plumbing": 0.45,
    "electrician": 0.45,
    "real estate": 0.40,
    "insurance": 0.70,
    "law firm": 0.90,
    "dentist": 0.65,
    "medical": 0.75,
    "marketing agency": 0.30,
    "construction": 0.40,
    "landscaping": 0.35,
    "pest control": 0.40,
    "restaurant": 0.10,
    "retail": 0.12,
}

DEFAULT_BASE_PRICE = 0.25

TIER1_METROS = {
    "new york", "los angeles", "san francisco", "chicago",
    "dallas", "austin", "miami", "seattle",
}

LARGE_METROS = {
    "houston", "phoenix", "philadelphia", "san antonio", "san jose",
    "jacksonville", "fort worth", "charlotte", "atlanta", "las vegas",
    "san diego", "denver", "nashville", "portland",
}

BULK_DISCOUNT_TIERS = [
    (10000, 0.45),
    (5000, 0.35),
    (1000, 0.25),
    (500, 0.18),
    (100, 0.10),
    (1, 0.0),
]

MIN_LEAD_PRICE = 0.05
MAX_LEAD_PRICE = 5.00


def get_bulk_discount(quantity: int) -> float:
    for min_qty, discount in BULK_DISCOUNT_TIERS:
        if quantity >= min_qty:
            return discount
    return 0.0


def calculate_lead_price(lead) -> float:
    industry_key = (lead.industry or "").lower().strip()
    base = INDUSTRY_BASE_PRICE.get(industry_key, DEFAULT_BASE_PRICE)

    # Lead type multiplier — consumer intent leads convert higher
    lead_type = getattr(lead, "lead_type", "business") or "business"
    type_multiplier = 1.5 if lead_type == "consumer" else 1.0

    # Data quality — use quality_score if available
    quality_score = getattr(lead, "quality_score", None)
    if quality_score is not None:
        quality = 1.0 + (quality_score / 100.0)  # maps 0-100 → 1.0-2.0
    else:
        has_phone = bool(lead.phone)
        has_email = bool(lead.email)
        has_website = bool(lead.website)
        if has_phone and has_email and has_website:
            quality = 2.0
        elif has_phone and has_email:
            quality = 1.8
        elif has_phone and has_website:
            quality = 1.2
        else:
            quality = 1.0

    # Location
    city_lower = (lead.city or "").lower().strip()
    if city_lower in TIER1_METROS:
        location = 1.40
    elif city_lower in LARGE_METROS:
        location = 1.25
    else:
        location = 1.10

    # Freshness
    if lead.scraped_date:
        days = (datetime.now(timezone.utc).replace(tzinfo=None) - lead.scraped_date).days
        if days <= 30:
            freshness = 1.30
        elif days <= 90:
            freshness = 1.15
        elif days <= 180:
            freshness = 1.05
        elif days <= 365:
            freshness = 1.00
        else:
            freshness = 0.80
    else:
        freshness = 1.05

    # AI conversion score — 1.0 when not yet scored (null), up to 1.5× uplift at score=100
    conversion_score = getattr(lead, "conversion_score", None)
    conversion_mult = 1.0 + (conversion_score / 100.0) * 0.5 if conversion_score is not None else 1.0

    # Reputation signals — review_count and yelp_rating add up to 1.35× premium
    # Businesses with many positive reviews are far more likely to close a sale
    yelp_rating = getattr(lead, "yelp_rating", None)
    review_count = getattr(lead, "review_count", None)
    reputation_mult = 1.0
    if review_count:
        if review_count >= 100:
            reputation_mult += 0.20
        elif review_count >= 25:
            reputation_mult += 0.12
        elif review_count >= 5:
            reputation_mult += 0.05
    if yelp_rating:
        if yelp_rating >= 4.5:
            reputation_mult += 0.15
        elif yelp_rating >= 4.0:
            reputation_mult += 0.08
        elif yelp_rating >= 3.5:
            reputation_mult += 0.03

    # Resale discount
    times_sold = getattr(lead, "times_sold", 0) or 0
    resale_mult = max(0.60, 1.0 - times_sold * 0.10)

    price = base * quality * conversion_mult * reputation_mult * location * freshness * resale_mult * type_multiplier
    price = max(MIN_LEAD_PRICE, min(MAX_LEAD_PRICE, price))
    return round(price, 4)


def calculate_purchase_total(avg_price: float, quantity: int) -> dict:
    discount = get_bulk_discount(quantity)
    subtotal = avg_price * quantity
    total = subtotal * (1 - discount)
    return {
        "avg_lead_price": round(avg_price, 4),
        "quantity": quantity,
        "subtotal": round(subtotal, 2),
        "discount_pct": int(discount * 100),
        "total": round(max(total, 0.50), 2),  # Stripe minimum $0.50
    }
