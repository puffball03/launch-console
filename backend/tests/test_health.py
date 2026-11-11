from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import create_app


def test_health_returns_ok():
    client = TestClient(create_app(load_settings({})))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_health_reports_fake_provider_without_key():
    client = TestClient(create_app(load_settings({})))

    assert client.get("/api/health").json()["provider"] == "fake"


def test_health_reports_foundry_provider_with_key():
    client = TestClient(create_app(load_settings({"ANTHROPIC_FOUNDRY_API_KEY": "test-key"})))

    assert client.get("/api/health").json()["provider"] == "foundry"
