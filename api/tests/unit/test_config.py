"""Spec api-authentication: fail closed without a usable token; tokens are never recorded."""

import pytest
from pydantic import ValidationError

from companion.config import Settings

VALID_TOKEN = "test-token-0123456789abcdef0123456789"
DB_URL = "postgresql+psycopg://user:db-secret-pw@db:5432/companion"


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("API_TOKEN", "DATABASE_URL", "ENABLE_DOCS", "LOG_LEVEL"):
        monkeypatch.delenv(name, raising=False)


def test_valid_construction_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_TOKEN", VALID_TOKEN)
    monkeypatch.setenv("DATABASE_URL", DB_URL)

    settings = Settings()

    assert settings.api_token.get_secret_value() == VALID_TOKEN
    assert settings.database_url.get_secret_value() == DB_URL
    assert settings.enable_docs is False
    assert settings.log_level == "INFO"


def test_missing_token_fails_naming_the_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)

    with pytest.raises(ValidationError) as exc:
        Settings()

    assert "api_token" in str(exc.value).lower()


def test_short_token_fails_without_printing_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_TOKEN", "short-token-value")
    monkeypatch.setenv("DATABASE_URL", DB_URL)

    with pytest.raises(ValidationError) as exc:
        Settings()

    assert "short-token-value" not in str(exc.value)


def test_repr_hides_secrets() -> None:
    settings = Settings(api_token=VALID_TOKEN, database_url=DB_URL)

    rendered = repr(settings) + str(settings)

    assert VALID_TOKEN not in rendered
    assert "db-secret-pw" not in rendered
