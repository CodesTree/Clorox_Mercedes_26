from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, sourced from environment variables / .env.

    SECURITY: database_url and the phase-05 credentials are secrets.
    Never log, print, or return them from any endpoint.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "sqlite:///./data/assetiq.db"
    fx_gbp_to_rm: float = 5.90
    cors_origins: str = "http://localhost:5173"
    scraper_user_agent: str = "AssetIQResearchBot/0.1 (+contact)"
    scraper_rate_limit_seconds: float = 4.0
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    gemini_api_key: str = ""
    google_calendar_credentials_json: str = "./secrets/google_sa.json"
    google_calendar_id: str = "primary"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
