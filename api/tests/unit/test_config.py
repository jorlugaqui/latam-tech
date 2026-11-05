"""Spec api-authentication: fail closed without a usable token; tokens are never recorded."""

import pytest
from pydantic import ValidationError

from companion.config import Settings

VALID_TOKEN = "test-token-0123456789abcdef0123456789"
DB_URL = "postgresql+psycopg://user:db-secret-pw@db:5432/companion"
TOOLS_URL = "http://mock-tools:8001"
TOOLS_TOKEN = "tools-token-0123456789abcdef01234567"
REQUIRED = {
    "api_token": VALID_TOKEN,
    "database_url": DB_URL,
    "tools_base_url": TOOLS_URL,
    "tools_api_token": TOOLS_TOKEN,
}


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "API_TOKEN",
        "DATABASE_URL",
        "ENABLE_DOCS",
        "LOG_LEVEL",
        "TOOLS_BASE_URL",
        "TOOLS_API_TOKEN",
        "TOOLS_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_valid_construction_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_TOKEN", VALID_TOKEN)
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("TOOLS_BASE_URL", TOOLS_URL)
    monkeypatch.setenv("TOOLS_API_TOKEN", TOOLS_TOKEN)

    settings = Settings()

    assert settings.api_token.get_secret_value() == VALID_TOKEN
    assert settings.database_url.get_secret_value() == DB_URL
    assert settings.enable_docs is False
    assert settings.log_level == "INFO"
    assert str(settings.tools_base_url).rstrip("/") == TOOLS_URL
    assert settings.tools_api_token.get_secret_value() == TOOLS_TOKEN
    assert settings.tools_timeout_seconds == 3


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
    settings = Settings(**REQUIRED)

    rendered = repr(settings) + str(settings)

    assert VALID_TOKEN not in rendered
    assert "db-secret-pw" not in rendered
    assert TOOLS_TOKEN not in rendered


def test_tools_base_url_is_required() -> None:
    values = {k: v for k, v in REQUIRED.items() if k != "tools_base_url"}

    with pytest.raises(ValidationError) as exc:
        Settings(**values)

    assert "tools_base_url" in str(exc.value).lower()


def test_tools_base_url_must_be_a_url() -> None:
    with pytest.raises(ValidationError):
        Settings(**{**REQUIRED, "tools_base_url": "not a url"})


def test_short_tools_token_fails_without_printing_it() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(**{**REQUIRED, "tools_api_token": "short-tools-token"})

    assert "short-tools-token" not in str(exc.value)
