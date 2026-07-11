"""Phase 4 — case coordination: routing, guarded state machine, audit, SLA.

Covers auto-routing by alert type, the raised->routed->ack->resolve happy path,
transition guards (409), the escalation ladder, SLA auto-escalation, audit
immutability, alert<->case linkage, and the absence of any financial-action
surface. Tests that mutate state depend on `reset_cases` for a clean slate, since
the seeded engine is shared across the session.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.core.models import Alert
from app.modules.alerts.service import run_detection
from app.modules.cases.models import Case, CaseEvent
from app.modules.cases.service import evaluate_escalations, get_case, history_of


@pytest.fixture()
def reset_cases(engine):
    """Regenerate alerts + cases to a fresh state before a mutating test."""
    with Session(engine) as session:
        run_detection(session)
    yield


# ---- helpers ----------------------------------------------------------------
def _first_case_of_type(session: Session, type_: str) -> Case:
    case = session.exec(
        select(Case).where(Case.type == type_).order_by(Case.id)
    ).first()
    assert case is not None, f"expected a seeded {type_} case"
    return case


# ---- auto-routing -----------------------------------------------------------
def test_auto_routing_by_type(client, db_session, reset_cases):
    liquidity = _first_case_of_type(db_session, "liquidity")
    anomaly = _first_case_of_type(db_session, "anomaly")

    assert liquidity.owner_role == "field_officer"
    assert liquidity.status == "routed"
    assert anomaly.owner_role == "risk_reviewer"
    assert anomaly.status == "routed"

    # Auto-creation populated advisory fields with safe language.
    for case in (liquidity, anomaly):
        assert case.next_step and case.recommended_action
        assert case.escalation_level == 0
        assert case.sla_minutes > 0


# ---- alert <-> case linkage -------------------------------------------------
def test_alert_case_linkage(db_session, reset_cases):
    for alert in db_session.exec(select(Alert)).all():
        assert alert.case_id is not None
        case = get_case(db_session, alert.case_id)
        assert case is not None
        assert case.alert_id == alert.id
        assert case.type == alert.type
        assert case.provider == alert.provider  # provider separation preserved


# ---- happy path + audit trail ----------------------------------------------
def test_happy_path_raised_to_resolved(client, db_session, reset_cases):
    case = _first_case_of_type(db_session, "anomaly")
    cid = case.id

    ack = client.post(f"/api/cases/{cid}/ack", json={"actor": "risk_reviewer"})
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"

    res = client.post(
        f"/api/cases/{cid}/resolve",
        json={"actor": "risk_reviewer", "note": "reviewed — salary payment"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "resolved"

    history = body["history"]
    assert [h["stage"] for h in history] == [
        "raised", "routed", "acknowledged", "resolved",
    ]
    # Actor attribution: system opens/routes, the reviewer acts.
    assert [h["actor"] for h in history] == [
        "system", "system", "risk_reviewer", "risk_reviewer",
    ]
    # Timestamps are non-decreasing in append order.
    assert [h["ts"] for h in history] == sorted(h["ts"] for h in history)
    assert history[-1]["detail"] == "reviewed — salary payment"


# ---- guards -----------------------------------------------------------------
def test_resolve_before_ack_is_409(client, db_session, reset_cases):
    case = _first_case_of_type(db_session, "anomaly")
    resp = client.post(f"/api/cases/{case.id}/resolve", json={"actor": "risk_reviewer"})
    assert resp.status_code == 409
    # Case is untouched by the rejected transition.
    fresh = client.get(f"/api/cases/{case.id}").json()
    assert fresh["status"] == "routed"
    assert len(fresh["history"]) == 2


def test_any_transition_on_resolved_case_is_409(client, db_session, reset_cases):
    case = _first_case_of_type(db_session, "anomaly")
    cid = case.id
    assert client.post(f"/api/cases/{cid}/ack", json={"actor": "risk_reviewer"}).status_code == 200
    assert client.post(f"/api/cases/{cid}/resolve", json={"actor": "risk_reviewer"}).status_code == 200

    for action in ("ack", "escalate", "resolve"):
        resp = client.post(f"/api/cases/{cid}/{action}", json={"actor": "supervisor"})
        assert resp.status_code == 409, f"{action} on a resolved case must be 409"


# ---- escalation ladder ------------------------------------------------------
def test_escalation_climbs_the_ladder(client, db_session, reset_cases):
    case = _first_case_of_type(db_session, "anomaly")  # base owner risk_reviewer
    cid = case.id

    first = client.post(f"/api/cases/{cid}/escalate", json={"actor": "risk_reviewer"}).json()
    assert first["escalation_level"] == 1
    assert first["owner_role"] == "supervisor"
    assert first["status"] == "escalated"

    second = client.post(f"/api/cases/{cid}/escalate", json={"actor": "supervisor"}).json()
    assert second["escalation_level"] == 2
    assert second["owner_role"] == "area_manager"
    assert second["status"] == "escalated"

    # A resolve after escalation is legal and closes the case.
    closed = client.post(f"/api/cases/{cid}/resolve", json={"actor": "area_manager"}).json()
    assert closed["status"] == "resolved"


# ---- SLA auto-escalation ----------------------------------------------------
def test_sla_auto_escalation(db_session, reset_cases):
    case = _first_case_of_type(db_session, "liquidity")  # base owner field_officer
    cid, sla = case.id, case.sla_minutes
    level_before = case.escalation_level
    events_before = len(history_of(db_session, cid))

    # Within SLA: nothing escalates.
    within = evaluate_escalations(db_session, case.updated_ts + timedelta(minutes=sla - 1))
    assert cid not in within
    db_session.refresh(case)
    assert case.escalation_level == level_before
    assert len(history_of(db_session, cid)) == events_before

    # Past SLA: this un-acked case auto-escalates with a system audit entry.
    past = evaluate_escalations(db_session, case.updated_ts + timedelta(minutes=sla + 1))
    assert cid in past
    db_session.refresh(case)
    assert case.escalation_level == level_before + 1
    assert case.owner_role == "supervisor"
    assert case.status == "escalated"

    trail = history_of(db_session, cid)
    assert len(trail) == events_before + 1
    last = trail[-1]
    assert last.actor == "system"
    assert last.stage == "escalated"
    assert last.detail == "auto-escalated: SLA exceeded"


# ---- audit immutability -----------------------------------------------------
def test_audit_history_is_append_only(client, db_session, reset_cases):
    case = _first_case_of_type(db_session, "anomaly")
    cid = case.id

    before = [
        (e.id, e.stage, e.actor, e.ts, e.detail) for e in history_of(db_session, cid)
    ]
    client.post(f"/api/cases/{cid}/ack", json={"actor": "risk_reviewer"})
    client.post(f"/api/cases/{cid}/escalate", json={"actor": "risk_reviewer"})

    after = history_of(db_session, cid)
    after_prefix = [(e.id, e.stage, e.actor, e.ts, e.detail) for e in after[: len(before)]]

    assert after_prefix == before, "existing audit entries must never change"
    assert len(after) == len(before) + 2  # only appends


# ---- no financial-action surface -------------------------------------------
def test_no_financial_action_surface(client):
    """No endpoint or case field transfers, blocks, freezes, or approves."""
    banned = ("transfer", "freeze", "block", "approve", "execute", "topup", "top_up",
              "withdraw", "deduct", "convert", "debit", "credit")
    spec = client.get("/openapi.json").json()

    for path, methods in spec["paths"].items():
        lower = path.lower()
        assert not any(b in lower for b in banned), f"unsafe path: {path}"

    # Case schema exposes only advisory/tracking fields.
    case_props = spec["components"]["schemas"]["CaseOut"]["properties"].keys()
    assert not any(b in name.lower() for name in case_props for b in banned)
