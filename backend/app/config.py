from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_publishable_key: str
    cors_origins: list[str] = ["http://localhost:3000"]
    # OpenAI — AI scoring and natural language search
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    # Email enrichment — Hunter.io
    hunter_api_key: str = ""
    # Cold email sending — Resend
    resend_api_key: str = ""
    resend_from_email: str = "leads@yourdomain.com"
    resend_from_name: str = "LeadGen"
    # Public site URL — used in email links
    site_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
