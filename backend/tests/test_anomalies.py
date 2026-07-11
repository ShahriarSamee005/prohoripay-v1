"""Anomaly test — labeled anomalies exist in the DB but never leak via any API.

Detection must earn its results (Phase 3): ground-truth labels are stored
server-side for validation only and must not appear in any response body.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.models import Transaction
from app.modules.synth.config import ANOMALIES, EXPECTED_ANOMALY_COUNT

_LEAKED_KEYS = {"is_injected_anomaly", "anomaly_type"}


def test_expected_labeled_anomalies_exist_in_db(db_session: Session):
    rows = db_session.exec(
        select(Transaction).where(Transaction.is_injected_anomaly == True)  # noqa: E712
    ).all()
    assert len(rows) == EXPECTED_ANOMALY_COUNT

    # Each configured anomaly type is present in the expected volume.
    by_type: dict[str, int] = {}
    for row in rows:
        assert row.anomaly_type is not None
        by_type[row.anomaly_type] = by_type.get(row.anomaly_type, 0) + 1
    for spec in ANOMALIES:
        assert by_type.get(spec.anomaly_type) == spec.count


def test_anomaly_labels_never_appear_in_transactions_api(client):
    # Request well beyond the dataset size so anomalies would surface if leaked.
    resp = client.get("/api/transactions", params={"limit": 1000})
    assert resp.status_code == 200
    body = resp.json()

    assert len(body["transactions"]) >= EXPECTED_ANOMALY_COUNT
    for txn in body["transactions"]:
        assert _LEAKED_KEYS.isdisjoint(txn.keys()), "ground-truth label leaked via API"


def test_anomaly_labels_never_appear_in_pools_or_agent_api(client):
    for path in ("/api/pools", "/api/agent"):
        raw = client.get(path).text
        assert "is_injected_anomaly" not in raw
        assert "anomaly_type" not in raw
