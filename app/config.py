from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE if _ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ai_provider: str = "gemini"
    ai_api_key: str = ""
    ai_model: str = "gemini-2.0-flash"
    demo_mode: bool = False
    auto_fallback_to_mock: bool = True
    batch_size_limit: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
