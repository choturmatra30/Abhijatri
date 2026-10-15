import pytest
from pydantic import ValidationError

from app.config import Settings, normalize_database_url

GOOD_PEPPER = "x" * 40
SUPABASE = (
    "postgresql://postgres.ref:pw@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"
    "?sslmode=require"
)


def _prod(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "database_url": SUPABASE,
        "receipt_pepper": GOOD_PEPPER,
        "cors_allowed_origins": "https://app.example.com",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize("prefix", ["postgres://", "postgresql://"])
def test_provider_urls_use_psycopg_driver(prefix: str) -> None:
    assert normalize_database_url(prefix + "u:p@h/db").startswith("postgresql+psycopg://")


def test_explicit_driver_is_untouched() -> None:
    url = "postgresql+psycopg://u:p@h/db"
    assert normalize_database_url(url) == url


def test_production_accepts_valid_configuration() -> None:
    settings = _prod()
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.docs_are_enabled is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_pepper": "development-only-change-me"},
        {"receipt_pepper": "y" * 26},
        {"cors_allowed_origins": "*"},
        {"database_url": SUPABASE.replace("?sslmode=require", "")},
    ],
)
def test_production_fails_closed(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        _prod(**overrides)


def test_development_keeps_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.docs_are_enabled is True
    assert settings.cors_origins == ["http://localhost:5173"]
