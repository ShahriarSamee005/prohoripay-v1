"""API-level alert tests: contract shape, safe language, no ground-truth leak."""

from __future__ import annotations

from app.modules.alerts.config import BANNED_WORDS

_META_KEYS = {"generated_at", "data_quality", "confidence_modifier"}
_ALERT_KEYS = {
    "id", "type", "severity", "label", "anomaly_type", "provider", "pool_id",
    "evidence", "baseline", "observed", "confidence", "ts", "case_id",
}


def test_alerts_endpoint_shape(client):
    resp = client.get("/api/alerts")
    assert resp.status_code == 200
    body = resp.json()

    assert _META_KEYS <= body["meta"].keys()
    assert "alerts" in body and "context" in body

    alerts = body["alerts"]
    assert alerts, "expected seeded alerts"
    types = {a["type"] for a in alerts}
    assert "anomaly" in types and "liquidity" in types

    for a in alerts:
        assert set(a.keys()) == _ALERT_KEYS
        assert a["type"] in {"anomaly", "liquidity"}
        assert a["severity"] in {"low", "medium", "high"}
        assert 0.0 <= a["confidence"] <= 1.0
        assert isinstance(a["evidence"], list) and len(a["evidence"]) >= 1
        assert isinstance(a["case_id"], str) and a["case_id"].startswith("case_")  # Phase 4
        if a["type"] == "liquidity":
            assert a["anomaly_type"] is None
            assert a["label"] == "liquidity pressure — requires attention"
        else:
            assert a["anomaly_type"] in {
                "structuring", "velocity_spike", "off_hours_burst", "balance_inconsistency"}
            assert a["label"] == "unusual — requires review"

    # Ordered by ts desc.
    ts_list = [a["ts"] for a in alerts]
    assert ts_list == sorted(ts_list, reverse=True)


def test_context_object_recognizes_active_event(client):
    body = client.get("/api/alerts").json()
    ctx = body["context"]
    assert ctx is not None
    assert ctx["active_event"] == "eid_rush"
    assert "expected" in ctx["note"].lower()


def test_liquidity_alert_for_physical_cash_has_null_provider(client):
    alerts = client.get("/api/alerts").json()["alerts"]
    liq = [a for a in alerts if a["type"] == "liquidity" and a["pool_id"] == "physical_cash"]
    assert liq, "expected a physical-cash liquidity alert"
    assert liq[0]["provider"] is None


def test_safe_language_everywhere(client):
    alerts = client.get("/api/alerts").json()["alerts"]
    for a in alerts:
        blob = (a["label"] + " " + " ".join(a["evidence"])).lower()
        for word in BANNED_WORDS:
            assert word.strip() not in blob, f"banned word {word!r} in alert {a['id']}"


def test_ground_truth_labels_never_leak(client):
    """Transaction ground-truth (is_injected_anomaly) and server-only fields absent.

    Note: `anomaly_type` DOES appear — it is the detector's *guess* (a contract
    field), not the stored ground-truth label on the transaction.
    """
    body = client.get("/api/alerts").json()
    raw = client.get("/api/alerts").text
    assert "is_injected_anomaly" not in raw
    assert "covered_txn_ids" not in raw
    # No individual alert exposes the server-side active_event memo.
    for a in body["alerts"]:
        assert "active_event" not in a
