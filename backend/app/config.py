from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://abhijatri:abhijatri_dev@localhost:5432/abhijatri"
    receipt_pepper: str = Field(
        default="development-only-change-me",
        min_length=24,
        repr=False,
    )
    receipt_session_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()

