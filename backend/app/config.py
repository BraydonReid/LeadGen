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
    # Email sending — Gmail SMTP (or any SMTP)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""        # your Gmail address
    smtp_password: str = ""    # Gmail App Password (16 chars)
    email_from_name: str = "Take Your Lead Today"
    email_from_address: str = ""  # defaults to smtp_user if blank
    # Public site URL — used in email links
    site_url: str = "http://localhost:3000"
    # Owner/test emails — downloads from these never increment times_sold
    owner_emails: list[str] = ["braydonreid01@gmail.com"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
