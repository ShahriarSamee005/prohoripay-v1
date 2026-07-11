"""Phase 0 test gate: /health returns 200 with status == "ok"."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    # A time field is present and looks like an ISO-8601 UTC string.
    assert "time" in body
    assert body["time"].endswith("Z")
