from functools import lru_cache
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_PEPPER = "development-only-change-me"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres"}


def normalize_database_url(value: str) -> str:
    """Make provider URLs (postgres://, postgresql://) use the psycopg3 driver."""
    for prefix in ("postgres://", "postgresql://"):
        if value.startswith(prefix):
            return "postgresql+psycopg://" + value[len(prefix) :]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://abhijatri:abhijatri_dev@localhost:5432/abhijatri"
    migration_database_url: str | None = None
    receipt_pepper: str = Field(default=DEFAULT_PEPPER, min_length=24, repr=False)
    receipt_session_minutes: int = 15
    cors_allowed_origins: str = "http://localhost:5173"
    log_level: str = "INFO"
    app_timezone: str = "UTC"
    default_display_timezone: str = "Asia/Dhaka"
    docs_enabled: bool | None = None
    db_pool_size: int = Field(default=5, ge=1, le=20)
    db_max_overflow: int = Field(default=2, ge=0, le=20)
    db_pool_recycle: int = Field(default=1800, ge=30)

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def _normalize_url(cls, value: str | None) -> str | None:
        return normalize_database_url(value) if value else value

    @field_validator("app_timezone")
    @classmethod
    def _storage_zone_is_utc(cls, value: str) -> str:
        if value != "UTC":
            raise ValueError("APP_TIMEZONE must be UTC; timestamps are stored and computed in UTC")
        return value

    @field_validator("default_display_timezone")
    @classmethod
    def _display_zone_exists(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"DEFAULT_DISPLAY_TIMEZONE {value!r} is not a valid IANA zone") from error
        return value

    @property
    def display_tz(self) -> ZoneInfo:
        return ZoneInfo(self.default_display_timezone)

    @property
    def is_production(self) -> bool:
        return self.app_env not in {"development", "test"}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def docs_are_enabled(self) -> bool:
        return self.docs_enabled if self.docs_enabled is not None else not self.is_production

    @property
    def effective_migration_url(self) -> str:
        return self.migration_database_url or self.database_url

    @model_validator(mode="after")
    def _production_guard(self) -> "Settings":
        if not self.is_production:
            return self
        if self.receipt_pepper == DEFAULT_PEPPER or len(self.receipt_pepper) < 32:
            raise ValueError("RECEIPT_PEPPER must be a unique value of at least 32 characters")
        if "*" in self.cors_origins or not self.cors_origins:
            raise ValueError("CORS_ALLOWED_ORIGINS must list explicit origins, never '*'")
        host = urlparse(self.database_url.replace("+psycopg", "", 1)).hostname or ""
        if host not in LOCAL_HOSTS and "sslmode=require" not in self.database_url:
            raise ValueError("DATABASE_URL must include sslmode=require outside local hosts")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
