from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok(make_settings):
    client = TestClient(create_app(make_settings()))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_health_reports_fake_provider_without_key(make_settings):
    client = TestClient(create_app(make_settings()))

    assert client.get("/api/health").json()["provider"] == "fake"


def test_health_reports_foundry_provider_with_key(make_settings):
    client = TestClient(create_app(make_settings(ANTHROPIC_FOUNDRY_API_KEY="test-key", ANTHROPIC_FOUNDRY_RESOURCE="mc-test")))

    assert client.get("/api/health").json()["provider"] == "foundry"
