"""Endpoint tests — the three Phase-1 endpoints return contract-shaped payloads."""

from __future__ import annotations

_META_KEYS = {"generated_at", "data_quality", "confidence_modifier"}


def test_get_agent(client):
    resp = client.get("/api/agent")
    assert resp.status_code == 200
    body = resp.json()

    assert body["id"] == "AGENT_07"
    assert body["name"] == "Karim Store"
    assert body["area"] == "Sylhet-Zindabazar"
    assert body["providers"] == ["bkash", "nagad", "rocket"]


def test_get_pools(client):
    resp = client.get("/api/pools")
    assert resp.status_code == 200
    body = resp.json()

    # meta envelope present and fresh.
    assert _META_KEYS <= body["meta"].keys()
    assert body["meta"]["data_quality"] == "ok"
    assert body["meta"]["confidence_modifier"] == 1.0

    pools = body["pools"]
    assert len(pools) == 4
    pool_ids = {p["pool_id"] for p in pools}
    assert pool_ids == {"physical_cash", "bkash", "nagad", "rocket"}

    # Physical cash is the shared pool (no provider, kind physical_cash) and first.
    assert pools[0]["pool_id"] == "physical_cash"
    physical = pools[0]
    assert physical["kind"] == "physical_cash"
    assert physical["provider"] is None
    assert physical["currency"] == "BDT"
    assert physical["status"] in {"healthy", "watch", "critical"}

    # Provider pools carry their provider and the provider_emoney kind.
    for p in pools[1:]:
        assert p["kind"] == "provider_emoney"
        assert p["provider"] == p["pool_id"]


def test_get_transactions(client):
    resp = client.get("/api/transactions")
    assert resp.status_code == 200
    body = resp.json()

    assert _META_KEYS <= body["meta"].keys()

    txns = body["transactions"]
    assert txns, "expected seeded transactions"
    assert len(txns) <= 50  # default limit

    first = txns[0]
    expected_keys = {
        "id", "ts", "provider", "txn_type", "amount", "status",
        "account_id", "area", "event_flag", "pool_effects",
    }
    assert expected_keys == set(first.keys())
    assert first["ts"].endswith("Z")
    assert first["amount"] > 0

    # pool_effects present and shaped as signed, pool-specific effects.
    effects = first["pool_effects"]
    assert len(effects) == 2
    for eff in effects:
        assert set(eff.keys()) == {"pool_id", "delta"}

    # Newest-first ordering.
    timestamps = [t["ts"] for t in txns]
    assert timestamps == sorted(timestamps, reverse=True)


def test_get_transactions_respects_limit_and_provider_filter(client):
    resp = client.get("/api/transactions", params={"limit": 5, "provider": "bkash"})
    assert resp.status_code == 200
    txns = resp.json()["transactions"]

    assert len(txns) <= 5
    assert all(t["provider"] == "bkash" for t in txns)


def test_get_transactions_rejects_unknown_provider(client):
    resp = client.get("/api/transactions", params={"provider": "paypal"})
    assert resp.status_code == 422
