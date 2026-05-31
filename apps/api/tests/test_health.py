from fastapi.testclient import TestClient

from app.routes import health
from app.main import app


def test_ready_reports_dependency_connectivity(monkeypatch):
    monkeypatch.setattr(health, "check_postgres", lambda: True)
    monkeypatch.setattr(health, "check_redis", lambda: True)
    monkeypatch.setattr(health, "check_worker", lambda: True)
    monkeypatch.setattr(health, "get_runtime_provider", lambda: type("R", (), {"name": "openclaw", "check_health": lambda self: False})())

    response = TestClient(app).get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["database_configured"] is True
    assert body["database_connected"] is True
    assert body["redis_connected"] is True
    assert body["worker_reachable"] is True
    assert body["openclaw_configured"] is True
    assert body["openclaw_reachable"] is False
