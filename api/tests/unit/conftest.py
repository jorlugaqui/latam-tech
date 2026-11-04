from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.config import Settings
from companion.main import create_app

TEST_TOKEN = "test-token-0123456789abcdef0123456789"


@pytest.fixture
def make_settings(tmp_path: Path) -> Callable[..., Settings]:
    """Settings from explicit test-only values; never from .env or the environment."""

    def _make(**overrides: object) -> Settings:
        values: dict[str, object] = {
            "api_token": TEST_TOKEN,
            "database_url": f"sqlite+pysqlite:///{tmp_path / 'app.db'}",
        }
        values.update(overrides)
        return Settings(**values)

    return _make


@pytest.fixture
def app(make_settings: Callable[..., Settings]) -> FastAPI:
    return create_app(make_settings())


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_TOKEN}"}
