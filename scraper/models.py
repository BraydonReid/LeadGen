from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True, unique=True)
    scraped_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    zip_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    full_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quality_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lead_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Reputation signals from API sources
    yelp_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    years_in_business: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
