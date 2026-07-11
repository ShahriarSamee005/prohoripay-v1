"""The SimulationClock — advances sim time, applies traffic, streams changes.

Each tick, deterministically: advance sim_time, generate + persist the next batch
of direction-aware transactions (updating pool balances), recompute forecasts,
run INCREMENTAL detection (new alerts + auto-created cases, without wiping the
human transitions on existing cases), run `evaluate_escalations(sim_time)`, then
publish typed SSE events.

Advisory only: controls generate synthetic events; nothing executes a real action.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.common.meta import make_meta
from app.core.effects import build_pool_effects
from app.core.enums import Provider, PoolStatus, TxnStatus
from app.core.models import Alert, Pool, Transaction
from app.core.seed import seed_database
from app.modules.alerts.config import MATCH_FRACTION
from app.modules.alerts.service import compute_alert_dicts, get_alerts
from app.modules.forecast.service import compute_forecasts
from app.modules.cases.models import Case
from app.modules.cases.service import (
    create_case_for_alert,
    get_case,
    system_close,
    evaluate_escalations,
)
from app.modules.synth import config as synth_cfg
from app.modules.sim import config as cfg
from app.modules.sim.broadcaster import Broadcaster
from app.modules.sim.generator import TickPlan, generate_tick

# Reuse the exact REST serializers so SSE payloads match the contract shapes.
from app.modules.alerts.router import _to_out as _alert_to_out
from app.modules.cases.router import _to_out as _case_to_out
from app.modules.forecast.router import _to_out as _forecast_to_out
from app.modules.pools.schemas import PoolOut

_POOL_ORDER = {"physical_cash": 0, "bkash": 1, "nagad": 2, "rocket": 3}


def _iso(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _seq_of(id_str: str) -> int:
    try:
        return int(str(id_str).split("_")[1])
    except (IndexError, ValueError):
        return 0


class SimulationClock:
    """Owns sim state, the tick loop, and the event broadcaster."""

    def __init__(self, engine, broadcaster: Broadcaster | None = None) -> None:
        self.engine = engine
        self.bus = broadcaster or Broadcaster()
        self.speed = cfg.DEFAULT_SPEED
        self.running = False

        self.sim_time = cfg.SIM_START
        self.tick_count = 0

        import numpy as np  # local: keeps import cost off module load
        self._np = np
        self.rng = np.random.RandomState(cfg.SIM_SEED)

        # provider -> {"data_quality", "confidence_modifier"}
        self.feeds: dict[str, dict] = {}
        self._eid_ticks = 0
        self._eid_intensity = "high"
        self._pending_inject: dict | None = None
        self._pending_events: list[dict] = []
        self._task: asyncio.Task | None = None
        self._primed = False

    # ---------------------------------------------------------------- state
    def snapshot(self) -> dict:
        return {
            "sim_time": _iso(self.sim_time),
            "tick": self.tick_count,
            "running": self.running,
            "speed": self.speed,
            "degraded_feeds": sorted(self.feeds.keys()),
        }

    def _freshness_by_pool(self) -> dict[str, float]:
        """Per-pool confidence multiplier from broken feeds (Scenario C)."""
        return {p: st["confidence_modifier"] for p, st in self.feeds.items()}

    def _meta(self):
        """Global meta envelope; worst broken feed drives data_quality down."""
        if not self.feeds:
            return make_meta()
        _, st = min(self.feeds.items(), key=lambda kv: kv[1]["confidence_modifier"])
        return make_meta(data_quality=st["data_quality"],
                         confidence_modifier=st["confidence_modifier"])

    # ------------------------------------------------------------- controls
    def start(self, speed: float | None = None) -> str:
        if speed:
            self.speed = float(speed)
        if not self.running:
            self.running = True
            try:
                loop = asyncio.get_running_loop()
                self._task = loop.create_task(self.run_loop())
            except RuntimeError:
                self._task = None  # no running loop (tests drive tick() directly)
        return f"clock running at {self.speed} ticks/sec"

    def pause(self) -> str:
        self.running = False
        return "clock paused"

    def reset(self) -> str:
        """Reseed to the initial scenario and clear all live sim state."""
        self.running = False
        seed_database(self.engine, reset=True)
        self.sim_time = cfg.SIM_START
        self.tick_count = 0
        self.rng = self._np.random.RandomState(cfg.SIM_SEED)
        self.feeds = {}
        self._eid_ticks = 0
        self._pending_inject = None
        self._pending_events = []
        self._primed = False
        return "reset to initial scenario"

    def eid_rush(self, provider: str = "physical_cash", intensity: str = "high") -> str:
        self._eid_ticks = cfg.EID_RUSH_TICKS
        self._eid_intensity = intensity if intensity in cfg.EID_INTENSITY_COUNT else "high"
        return (f"eid_rush ({self._eid_intensity}) for {cfg.EID_RUSH_TICKS} ticks — "
                "sustained cash-out pressure on physical cash")

    def inject_anomaly(self, provider: str = "rocket",
                       type: str = cfg.DEFAULT_INJECT_TYPE) -> str:
        atype = type if type in cfg.INJECT_PRESETS else cfg.DEFAULT_INJECT_TYPE
        self._pending_inject = {"provider": provider, "type": atype}
        return f"injected {atype} cluster on {provider} — detection catches it next tick"

    def break_feed(self, provider: str, mode: str = cfg.DEFAULT_FEED_MODE) -> str:
        quality, modifier = cfg.FEED_MODES.get(mode, cfg.FEED_MODES[cfg.DEFAULT_FEED_MODE])
        self.feeds[provider] = {"data_quality": quality, "confidence_modifier": modifier}
        self._pending_events.append({
            "type": "feed_status",
            "data": {"provider": provider, "data_quality": quality,
                     "confidence_modifier": modifier},
        })
        return f"{provider} feed marked {mode} — confidence degraded (advisory caution)"

    def restore_feed(self, provider: str) -> str:
        self.feeds.pop(provider, None)
        self._pending_events.append({
            "type": "feed_status",
            "data": {"provider": provider, "data_quality": "ok",
                     "confidence_modifier": 1.0},
        })
        return f"{provider} feed restored to ok"

    async def flush_and_publish(self) -> None:
        """Emit any events queued by controls (e.g. feed_status) immediately."""
        pending, self._pending_events = self._pending_events, []
        for event in pending:
            await self.bus.publish(event)

    # ------------------------------------------------------------ tick loop
    async def run_loop(self) -> None:
        try:
            while self.running:
                await self.tick()
                await asyncio.sleep(1.0 / max(self.speed, 0.001))
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            pass

    async def tick(self) -> dict:
        """Advance one tick: apply traffic, recompute, detect, escalate, publish."""
        await self.flush_and_publish()

        with Session(self.engine) as session:
            self.sim_time += timedelta(minutes=cfg.SIM_MINUTES_PER_TICK)
            self.tick_count += 1

            if not self._primed:  # start each seeded case's SLA clock at sim-start
                self._prime_case_clocks(session)
                self._primed = True

            self._apply_transactions(session, self._plan_for_tick())
            session.commit()

            fb = self._freshness_by_pool()
            forecasts = compute_forecasts(session, freshness_by_pool=fb)
            new_alerts, changed_cases = self._detect_incremental(session, fb)

            for case_id in evaluate_escalations(session, self.sim_time):
                case = get_case(session, case_id)
                if case is not None:
                    changed_cases.append(case)
            session.commit()

            # Build payloads while the session is open.
            tick_data = {"sim_time": _iso(self.sim_time), "tick": self.tick_count}
            balance_data = self._balance_payload(session, forecasts)
            forecast_data = {
                "forecasts": [_forecast_to_out(r).model_dump() for r in forecasts],
                "meta": self._meta().model_dump(),
            }
            alert_events = [{"alert": _alert_to_out(a).model_dump()} for a in new_alerts]
            case_events, seen = [], set()
            for case in changed_cases:
                if case.id in seen:
                    continue
                seen.add(case.id)
                case_events.append({"case": _case_to_out(session, case).model_dump()})

        await self.bus.publish({"type": "tick", "data": tick_data})
        await self.bus.publish({"type": "balance_update", "data": balance_data})
        await self.bus.publish({"type": "forecast_update", "data": forecast_data})
        for event in alert_events:
            await self.bus.publish({"type": "alert_new", "data": event})
        for event in case_events:
            await self.bus.publish({"type": "case_update", "data": event})

        return {"tick": self.tick_count, "new_alerts": len(alert_events),
                "changed_cases": len(case_events)}

    # ----------------------------------------------------------- tick internals
    def _plan_for_tick(self) -> TickPlan:
        plan = TickPlan()
        if self._eid_ticks > 0:
            plan.eid_cashout_count = cfg.EID_INTENSITY_COUNT.get(self._eid_intensity, 8)
            self._eid_ticks -= 1
        if self._pending_inject is not None:
            plan.inject_type = self._pending_inject["type"]
            plan.inject_provider = self._pending_inject["provider"]
            self._pending_inject = None
        return plan

    def _prime_case_clocks(self, session: Session) -> None:
        """Rebase open seeded cases' SLA clock to sim-start so they don't all
        fire auto-escalation on tick 1 (their historical opened_ts predates the
        sim clock). opened_ts is kept for traceability; only updated_ts is moved.
        """
        for case in session.exec(select(Case)).all():
            if case.status != "resolved":
                case.updated_ts = cfg.SIM_START
                session.add(case)
        session.commit()

    def _next_txn_seq(self, session: Session) -> int:
        ids = session.exec(select(Transaction.id)).all()
        return max((_seq_of(i) for i in ids), default=0) + 1

    def _apply_transactions(self, session: Session, plan: TickPlan) -> list[Transaction]:
        raws = generate_tick(self.rng, plan)
        if not raws:
            return []
        seq = self._next_txn_seq(session)
        pools = {p.pool_id: p for p in session.exec(select(Pool)).all()}
        agent = synth_cfg.AGENTS[0]

        added: list[Transaction] = []
        for r in raws:
            effects = build_pool_effects(r.txn_type, Provider(r.provider), r.amount)
            for eff in effects:  # apply signed, pool-specific balance movement
                pool = pools.get(eff["pool_id"])
                if pool is not None:
                    pool.current_balance += int(eff["delta"])
            txn = Transaction(
                id=f"txn_{seq:05d}", agent_id=agent.id, ts=self.sim_time,
                provider=r.provider, txn_type=r.txn_type, amount=r.amount,
                status=TxnStatus.completed, account_id=r.account_id, area=agent.area,
                event_flag=r.event_flag, pool_effects=effects,
                is_injected_anomaly=r.is_injected_anomaly, anomaly_type=r.anomaly_type,
            )
            session.add(txn)
            added.append(txn)
            seq += 1
        for pool in pools.values():
            session.add(pool)
        return added

    def _detect_incremental(self, session: Session, fb: dict[str, float]):
        """Create only NEW alerts/cases; keep existing cases + their history intact.

        Anomalies: an alert is new when its covered transactions don't materially
        overlap an existing anomaly alert. Liquidity: one open alert per pool —
        create when a pool enters pressure, refresh confidence while it persists,
        and auto-close (system) when the pool recovers.
        """
        dicts = compute_alert_dicts(session, fb)
        existing = get_alerts(session)
        new_alerts: list[Alert] = []
        changed_cases: list = []
        alert_seq = max((_seq_of(a.id) for a in existing), default=0) + 1
        case_seq = max((_seq_of(c) for c in session.exec(select(Case.id)).all()), default=0) + 1

        def persist(d: dict) -> Alert:
            nonlocal alert_seq
            alert = Alert(id=f"alert_{alert_seq:04d}", case_id=None, **d)
            session.add(alert)
            session.flush()
            alert_seq += 1
            return alert

        def open_case_for(alert: Alert):
            nonlocal case_seq
            case = create_case_for_alert(session, alert, case_seq)
            case_seq += 1
            return case

        # --- anomalies (event-based, persist) ---
        existing_anom = [a for a in existing if a.type == "anomaly"]
        for d in (x for x in dicts if x["type"] == "anomaly"):
            if _overlaps_any(d["covered_txn_ids"], existing_anom):
                continue
            alert = persist(d)
            changed_cases.append(open_case_for(alert))
            new_alerts.append(alert)
            existing_anom.append(alert)

        # --- liquidity (stateful reflection of current forecast pressure) ---
        detected_liq = {d["pool_id"]: d for d in dicts if d["type"] == "liquidity"}
        open_liq: dict[str, tuple] = {}
        for a in existing:
            if a.type == "liquidity" and a.case_id:
                case = get_case(session, a.case_id)
                if case is not None and case.status != "resolved":
                    open_liq[a.pool_id] = (a, case)

        for pool_id, d in detected_liq.items():
            if pool_id not in open_liq:
                alert = persist(d)
                changed_cases.append(open_case_for(alert))
                new_alerts.append(alert)
            else:  # refresh the live alert (so a broken feed lowers its confidence)
                alert, _ = open_liq[pool_id]
                alert.severity = d["severity"]
                alert.confidence = d["confidence"]
                alert.evidence = d["evidence"]
                alert.baseline = d["baseline"]
                alert.observed = d["observed"]
                session.add(alert)

        for pool_id, (_, case) in open_liq.items():
            if pool_id not in detected_liq:  # pressure eased -> auto-close (system)
                system_close(session, case, self.sim_time,
                             "liquidity pressure eased — auto-closed")
                changed_cases.append(case)

        session.flush()
        return new_alerts, changed_cases

    def _balance_payload(self, session: Session, forecasts) -> dict:
        status_by = {r.pool_id: r.status for r in forecasts}
        pools = sorted(session.exec(select(Pool)).all(),
                       key=lambda p: _POOL_ORDER.get(p.pool_id, 99))
        items = [
            PoolOut(
                pool_id=p.pool_id, kind=p.kind.value, provider=p.provider,
                label=p.label, balance=p.current_balance, currency=p.currency,
                status=status_by.get(p.pool_id, PoolStatus.healthy).value,
            ).model_dump()
            for p in pools
        ]
        return {"pools": items, "meta": self._meta().model_dump()}


def _overlaps_any(covered: list[str], existing_anom: list[Alert],
                  frac: float = MATCH_FRACTION) -> bool:
    """True if `covered` overlaps any existing anomaly alert's coverage >= frac."""
    if not covered:
        return False
    cov = set(covered)
    for a in existing_anom:
        prior = set(a.covered_txn_ids or [])
        if prior and len(cov & prior) / len(cov) >= frac:
            return True
    return False
