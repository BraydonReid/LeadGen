import stripe

from app.config import settings

stripe.api_key = settings.stripe_secret_key

PRICE_MAP = {
    100: 900,    # $9.00
    500: 2900,   # $29.00
    1000: 4900,  # $49.00
}

VALID_QUANTITIES = list(PRICE_MAP.keys())


def create_checkout_session(
    industry: str,
    state: str,
    city: str | None,
    quantity: int,
    success_url: str,
    cancel_url: str,
) -> stripe.checkout.Session:
    amount_cents = PRICE_MAP[quantity]

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": amount_cents,
                    "product_data": {
                        "name": f"{quantity} {industry.title()} Leads ({state.upper()})",
                        "description": f"CSV download of {quantity} business leads",
                    },
                },
                "quantity": 1,
            }
        ],
        metadata={
            "industry": industry,
            "state": state,
            "city": city or "",
            "quantity": str(quantity),
        },
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return session
