from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_publishable_key: str
    cors_origins: list[str] = ["http://localhost:3000"]
    ollama_base_url: str = "http://ollama:11434"
    ollama_scoring_model: str = "llama3.1:8b"
    ollama_search_model: str = "llama3.1:8b"
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
