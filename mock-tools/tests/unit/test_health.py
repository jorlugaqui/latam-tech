from fastapi.testclient import TestClient

from mock_tools.main import create_app


def test_live() -> None:
    response = TestClient(create_app()).get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
