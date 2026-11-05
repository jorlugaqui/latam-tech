from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from mock_tools.main import create_app
from mock_tools.settings import MockToolsSettings

TOOLS_TOKEN = "test-tools-token-0123456789abcdef0123"
# The brief's reference instant: fixtures come back exactly as written.
REFERENCE = datetime(2026, 9, 15, 11, 2, 33, tzinfo=UTC)


@pytest.fixture
def settings() -> MockToolsSettings:
    return MockToolsSettings(tools_api_token=TOOLS_TOKEN)


@pytest.fixture
def client(settings: MockToolsSettings) -> TestClient:
    return TestClient(create_app(settings, clock=lambda: REFERENCE))


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOOLS_TOKEN}"}
