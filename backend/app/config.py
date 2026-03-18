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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
