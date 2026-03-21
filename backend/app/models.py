from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True, unique=True)
    scraped_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    times_sold: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    zip_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    full_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quality_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lead_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="business")
    # AI scoring fields — null until background job processes the lead
    conversion_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, index=True)
    website_quality_signal: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    contact_richness_signal: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    ai_scored_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Reputation signals from Yelp/Foursquare — major differentiator vs Apollo/ZoomInfo
    yelp_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    years_in_business: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # Email enrichment — Hunter.io discovered emails
    email_source: Mapped[str | None] = mapped_column(String(20), nullable=True)   # 'scraper' | 'hunter'
    email_found_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    enrichment_attempted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    stripe_session_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_lead_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fulfilled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    zip_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    radius_miles: Mapped[float | None] = mapped_column(Integer, nullable=True)
    buyer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)


class LeadCredit(Base):
    __tablename__ = "lead_credits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    discount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SampleRequest(Base):
    __tablename__ = "sample_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("email", "industry", "state", name="uq_sample_email_industry_state"),
    )


class IndustryDemand(Base):
    __tablename__ = "industry_demand"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    purchase_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    leads_sold: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    revenue_cents: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("industry", "state", "city", name="uq_demand_industry_state_city"),
    )


class EmailCampaign(Base):
    __tablename__ = "email_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")  # draft|active|paused|complete
    industry_filter: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state_filter: Mapped[str | None] = mapped_column(String(2), nullable=True)
    city_filter: Mapped[str | None] = mapped_column(String(100), nullable=True)
    template_subject: Mapped[str] = mapped_column(String(500), nullable=False)
    template_body_html: Mapped[str] = mapped_column(Text, nullable=False)
    from_name: Mapped[str] = mapped_column(String(100), nullable=False, server_default="LeadGen")
    from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence_days: Mapped[str] = mapped_column(String(50), nullable=False, server_default="0,3,8")
    emails_sent: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    emails_opened: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    emails_clicked: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EmailSend(Base):
    __tablename__ = "email_sends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence_step: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_send_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    unsubscribe_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    resend_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


class EmailUnsubscribe(Base):
    """Global unsubscribe list — checked before every send."""
    __tablename__ = "email_unsubscribes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    unsubscribed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
