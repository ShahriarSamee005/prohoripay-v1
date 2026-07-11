"""Phase 5 — simulation clock + SSE stream + presenter controls.

Tick effects are driven deterministically by calling the clock directly inside a
fresh event loop (`asyncio.run`), each test on its OWN seeded engine so the shared
session engine is never mutated. HTTP control endpoints are covered separately for
their `{ ok, applied }` shape. The live SSE frames themselves are demonstrated by
the captured curl snippet in the phase write-up.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, select

from app.core.db import get_session
from app.core.models import Alert
from app.core.seed import seed_database
from app.main import app
from app.modules.cases.models import Case, CaseEvent
from app.modules.sim.clock import SimulationClock
from app.modules.sim.service import set_clock


# --------------------------------------------------------------------- helpers
@pytest.fixture()
def clock(tmp_path):
    """A SimulationClock bound to a fresh, isolated seeded engine."""
    db_path = tmp_path / "sim.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    seed_database(engine, reset=True)
    return SimulationClock(engine)


def _run(coro):
    return asyncio.run(coro)


def _drain(queue) -> list[dict]:
    out = []
    while not queue.empty():
        out.append(queue.get_nowait())
    return out


def _of_type(events, type_):
    return [e for e in events if e["type"] == type_]


def _last_forecast(events):
    fus = _of_type(events, "forecast_update")
    return fus[-1]["data"] if fus else None


def _pool_forecast(forecast_data, pool_id):
    return next(f for f in forecast_data["forecasts"] if f["pool_id"] == pool_id)


# ------------------------------------------------------------- stream smoke
def test_stream_smoke_tick_and_balance(clock):
    """A subscriber receives tick + balance_update (+ forecast_update) on a tick."""
    async def go():
        queue = clock.bus.subscribe()
        await clock.tick()
        return _drain(queue)

    events = _run(go())
    types = [e["type"] for e in events]
    assert "tick" in types
    assert "balance_update" in types
    assert "forecast_update" in types

    tick = _of_type(events, "tick")[0]["data"]
    assert tick["tick"] == 1 and tick["sim_time"].endswith("Z")
    balance = _of_type(events, "balance_update")[0]["data"]
    assert len(balance["pools"]) == 4
    assert {"generated_at", "data_quality", "confidence_modifier"} <= balance["meta"].keys()


# ------------------------------------------------------------- eid_rush
def test_eid_rush_drives_liquidity_alert(clock):
    """eid_rush pushes physical cash into a liquidity alert within a few ticks."""
    async def go():
        queue = clock.bus.subscribe()
        clock.eid_rush(intensity="high")
        for _ in range(4):
            await clock.tick()
        return _drain(queue)

    events = _run(go())
    phys = _pool_forecast(_last_forecast(events), "physical_cash")
    assert phys["status"] == "critical"  # calm never reaches this; eid_rush caused it

    with Session(clock.engine) as session:
        liq = [
            a for a in session.exec(select(Alert)).all()
            if a.type == "liquidity" and a.pool_id == "physical_cash"
        ]
        assert liq, "expected a physical-cash liquidity alert after eid_rush"
        assert liq[-1].provider is None


# ------------------------------------------------------------- inject_anomaly
def test_inject_anomaly_creates_alert_and_case(clock):
    """inject_anomaly -> a matching anomaly alert + auto-created case, end to end."""
    async def go():
        queue = clock.bus.subscribe()
        clock.inject_anomaly(provider="rocket", type="structuring")
        for _ in range(2):
            await clock.tick()
        return _drain(queue)

    events = _run(go())
    anomalies = [
        e for e in _of_type(events, "alert_new")
        if e["data"]["alert"]["type"] == "anomaly"
        and e["data"]["alert"]["provider"] == "rocket"
    ]
    assert anomalies, "expected a new anomaly alert on the injected provider"
    alert = anomalies[-1]["data"]["alert"]
    assert alert["anomaly_type"] == "structuring"
    assert alert["case_id"] is not None

    # A case_update for the auto-created case was streamed, owned by risk_reviewer.
    case_updates = [
        e for e in _of_type(events, "case_update")
        if e["data"]["case"]["id"] == alert["case_id"]
    ]
    assert case_updates
    case = case_updates[-1]["data"]["case"]
    assert case["type"] == "anomaly" and case["owner_role"] == "risk_reviewer"
    assert case["alert_id"] == alert["id"]


# ------------------------------------------------------------- break_feed / restore
def test_break_feed_degrades_then_restore_recovers(clock):
    """break_feed drops a provider's forecast confidence + marks meta stale and
    emits feed_status; restore_feed returns it to ok and confidence recovers."""
    async def go():
        queue = clock.bus.subscribe()
        await clock.tick()                       # fresh baseline
        fresh = _drain(queue)

        clock.break_feed(provider="nagad", mode="stale")
        await clock.flush_and_publish()
        await clock.tick()
        broken = _drain(queue)

        clock.restore_feed(provider="nagad")
        await clock.flush_and_publish()
        await clock.tick()
        restored = _drain(queue)
        return fresh, broken, restored

    fresh, broken, restored = _run(go())

    fresh_conf = _pool_forecast(_last_forecast(fresh), "nagad")["confidence"]

    # feed_status emitted, meta degraded, nagad confidence dropped.
    fs = _of_type(broken, "feed_status")
    assert any(e["data"]["provider"] == "nagad"
               and e["data"]["data_quality"] == "stale"
               and e["data"]["confidence_modifier"] < 1.0 for e in fs)
    broken_fc = _last_forecast(broken)
    assert broken_fc["meta"]["data_quality"] == "stale"
    assert broken_fc["meta"]["confidence_modifier"] < 1.0
    broken_conf = _pool_forecast(broken_fc, "nagad")["confidence"]
    assert broken_conf < fresh_conf, "broken feed must lower confidence"

    # restore -> ok meta + feed_status ok + confidence recovers above the broken value.
    fs3 = _of_type(restored, "feed_status")
    assert any(e["data"]["provider"] == "nagad"
               and e["data"]["data_quality"] == "ok" for e in fs3)
    restored_fc = _last_forecast(restored)
    assert restored_fc["meta"]["data_quality"] == "ok"
    restored_conf = _pool_forecast(restored_fc, "nagad")["confidence"]
    assert restored_conf > broken_conf, "confidence must recover after restore"


# ------------------------------------------------------------- auto-escalation
def test_auto_escalation_fires_on_ticks_past_sla(clock):
    """A case created in the sim auto-escalates once sim_time passes its SLA."""
    async def go():
        clock.inject_anomaly(provider="rocket", type="structuring")
        await clock.tick()  # creates the injected anomaly case at this sim_time
        with Session(clock.engine) as session:
            alerts = [
                a for a in session.exec(select(Alert)).all()
                if a.anomaly_type == "structuring" and a.provider == "rocket"
            ]
            assert alerts, "injected anomaly alert not created"
            case_id = alerts[0].case_id
            case = session.get(Case, case_id)
            level_before = case.escalation_level
        # Advance well past the anomaly SLA (30 sim-min = 6 ticks).
        for _ in range(8):
            await clock.tick()
        return case_id, level_before

    case_id, level_before = _run(go())
    with Session(clock.engine) as session:
        case = session.get(Case, case_id)
        assert case.escalation_level > level_before
        events = session.exec(
            select(CaseEvent).where(CaseEvent.case_id == case_id)
        ).all()
        assert any(e.actor == "system" and "auto-escalated" in e.detail for e in events)


# ------------------------------------------------------------- multi-subscriber
def test_multiple_subscribers_and_disconnect_cleanup(clock):
    """Every subscriber gets the broadcast; unsubscribing cleans up without error."""
    async def go():
        q1 = clock.bus.subscribe()
        q2 = clock.bus.subscribe()
        await clock.tick()
        n1, n2 = len(_drain(q1)), len(_drain(q2))

        clock.bus.unsubscribe(q1)          # simulate a disconnect
        await clock.tick()
        n2_after = len(_drain(q2))
        return n1, n2, n2_after, clock.bus.subscriber_count

    n1, n2, n2_after, remaining = _run(go())
    assert n1 > 0 and n2 == n1            # both saw the same broadcast
    assert n2_after > 0                    # survivor keeps receiving
    assert remaining == 1                  # the disconnected queue was removed


# ------------------------------------------------------------- HTTP controls
def test_control_endpoints_return_ok_applied(tmp_path):
    """Each control endpoint returns { ok: true, applied: <str> }."""
    db_path = tmp_path / "http.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    seed_database(engine, reset=True)
    set_clock(SimulationClock(engine))

    def _override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override
    try:
        with TestClient(app) as client:
            calls = [
                ("/api/sim/start", {"speed": 1}),
                ("/api/sim/pause", None),
                ("/api/sim/eid_rush", {"provider": "physical_cash", "intensity": "high"}),
                ("/api/sim/inject_anomaly", {"provider": "bkash", "type": "structuring"}),
                ("/api/sim/break_feed", {"provider": "nagad", "mode": "stale"}),
                ("/api/sim/restore_feed", {"provider": "nagad"}),
                ("/api/sim/pause", None),
                ("/api/sim/reset", None),
            ]
            for path, body in calls:
                resp = client.post(path, json=body)
                assert resp.status_code == 200, (path, resp.text)
                data = resp.json()
                assert data["ok"] is True
                assert isinstance(data["applied"], str) and data["applied"]
    finally:
        app.dependency_overrides.clear()
        set_clock(None)


# ------------------------------------------------------------- safety
def test_no_financial_action_in_sim_surface(tmp_path):
    """No sim path or control transfers, blocks, freezes, or approves anything."""
    with TestClient(app) as client:
        spec = client.get("/openapi.json").json()
    banned = ("transfer", "freeze", "block", "approve", "execute",
              "withdraw", "deduct", "convert", "debit", "credit")
    sim_paths = [p for p in spec["paths"] if "/sim/" in p or p.endswith("/stream")]
    assert sim_paths, "expected sim endpoints in the schema"
    for path in sim_paths:
        assert not any(b in path.lower() for b in banned), f"unsafe sim path: {path}"
