from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://aye:aye@localhost:5432/aye"
    cors_origins: str = "http://localhost:3000"
    rss_feed_urls: str = ""
    max_feed_bytes: int = Field(default=2_000_000, ge=4096, le=20_000_000)
    max_production_attempts: int = Field(default=3, ge=1, le=10)
    production_stale_after_seconds: int = Field(default=21600, ge=60, le=172800)
    media_dir: str = "media"
    ffmpeg_binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"
    api_token: str | None = None

    model_config = SettingsConfigDict(env_prefix="AYE_", env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
