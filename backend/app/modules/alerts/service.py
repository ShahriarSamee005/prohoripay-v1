"""Alert orchestration: run detectors + liquidity forecasts, persist, serve.

Anomaly alerts come from the deterministic rule detectors (optionally nudged by
a secondary IsolationForest that can only RAISE confidence on an already-evidenced
hit). Liquidity alerts are derived from Phase-2 forecasts. Everything is persisted
with stable IDs so Phase 4 can attach cases.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, delete, select

from app.core.enums import PoolId, PoolStatus
from app.core.models import Alert, Pool, Transaction
from app.modules.alerts.config import (
    ANOMALY_LABEL,
    DEFAULT_DETECTOR_CONFIG,
    EVENT_CALENDAR,
    LIQUIDITY_ALERT_STATUSES,
    LIQUIDITY_LABEL,
    DetectorConfig,
)
from app.modules.alerts.detectors import (
    Finding,
    active_event,
    detect_balance_inconsistency,
    detect_off_hours,
    detect_structuring,
    detect_velocity,
)
from app.modules.forecast.service import compute_forecasts


# ------------------------------------------------------------------ data loading
def _load_txn_records(session: Session) -> list[dict]:
    rows = session.exec(select(Transaction)).all()
    return [
        {
            "id": t.id, "ts": t.ts, "provider": t.provider, "amount": t.amount,
            "account_id": t.account_id, "event_flag": t.event_flag,
            "txn_type": t.txn_type.value,
        }
        for t in rows
    ]


def _net_by_pool(session: Session) -> tuple[dict[str, int], datetime | None]:
    net: dict[str, int] = {}
    anchor: datetime | None = None
    for t in session.exec(select(Transaction)).all():
        anchor = t.ts if anchor is None or t.ts > anchor else anchor
        for eff in t.pool_effects:
            net[eff["pool_id"]] = net.get(eff["pool_id"], 0) + int(eff["delta"])
    return net, anchor


# --------------------------------------------------------- IsolationForest (2nd)
def _isolation_forest_bump(
    findings: list[Finding],
    txns: list[dict],
    cfg: DetectorConfig,
) -> dict[int, float]:
    """Optional secondary signal. Returns {finding_index: confidence_bump}.

    Fits an IsolationForest per provider on (amount, inter-arrival, account
    frequency) and bumps confidence for findings whose covered transactions are
    largely flagged as outliers. It NEVER creates a finding on its own.
    """
    if not cfg.isolation_forest_enabled:
        return {}
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest
    except Exception:
        return {}

    # Per-provider outlier set.
    outliers: set[str] = set()
    by_provider: dict[str, list[dict]] = {}
    for t in txns:
        by_provider.setdefault(t["provider"], []).append(t)

    for items in by_provider.values():
        if len(items) < 8:
            continue
        items = sorted(items, key=lambda t: t["ts"])
        freq: dict[str, int] = {}
        for t in items:
            freq[t["account_id"]] = freq.get(t["account_id"], 0) + 1
        feats, ids = [], []
        prev_ts = None
        for t in items:
            inter = 0.0 if prev_ts is None else (t["ts"] - prev_ts).total_seconds()
            prev_ts = t["ts"]
            feats.append([float(t["amount"]), inter, float(freq[t["account_id"]])])
            ids.append(t["id"])
        try:
            model = IsolationForest(
                contamination=cfg.isolation_forest_contamination,
                random_state=cfg.isolation_forest_random_state,
            )
            preds = model.fit_predict(np.array(feats, dtype=float))
        except Exception:
            continue
        outliers.update(tid for tid, p in zip(ids, preds) if p == -1)

    bumps: dict[int, float] = {}
    for i, f in enumerate(findings):
        if not f.covered_txn_ids:
            continue
        frac = sum(1 for tid in f.covered_txn_ids if tid in outliers) / len(f.covered_txn_ids)
        if frac >= 0.5:
            bumps[i] = cfg.isolation_forest_confidence_bump
    return bumps


# --------------------------------------------------------------- alert building
def _severity_from_confidence(conf: float) -> str:
    if conf >= 0.8:
        return "high"
    if conf >= 0.6:
        return "medium"
    return "low"


def _finding_confidence(f: Finding, bump: float, data_freshness: float,
                        cfg: DetectorConfig) -> float:
    # Earned: deviation strength x context x data freshness (+ IF bump, capped).
    context_factor = cfg.context_penalty_for_volume if (
        f.within_event and f.anomaly_type == "velocity_spike") else 1.0
    conf = f.strength * context_factor * data_freshness + bump
    return round(max(0.0, min(0.98, conf)), 2)


def _forecast_liquidity_alerts(session, data_freshness, anchor):
    """Build liquidity alerts from Phase-2 forecasts (status critical/watch)."""
    alerts: list[dict] = []
    for fc in compute_forecasts(session, data_freshness=data_freshness):
        if fc.status not in LIQUIDITY_ALERT_STATUSES:
            continue
        provider = None if fc.pool_id == PoolId.physical_cash.value else fc.pool_id
        severity = "high" if fc.status == PoolStatus.critical else "medium"
        alerts.append({
            "type": "liquidity", "severity": severity, "label": LIQUIDITY_LABEL,
            "anomaly_type": None, "provider": provider, "pool_id": fc.pool_id,
            "evidence": fc.evidence,
            "baseline": {"burn_rate_per_min": fc.burn_rate_per_min, "safety_floor_aware": True},
            "observed": {"minutes_to_depletion": fc.minutes_to_depletion,
                         "current_balance": fc.current_balance, "trend": fc.trend},
            "confidence": fc.confidence,
            "ts": fc.projected_depletion_ts or anchor or datetime.utcnow(),
            "covered_txn_ids": [], "active_event": None,
        })
    return alerts


# ------------------------------------------------------------------- public API
def run_detection(session: Session, data_freshness: float = 1.0,
                  cfg: DetectorConfig = DEFAULT_DETECTOR_CONFIG) -> dict:
    """(Re)compute all alerts over the seeded history + current forecasts, persist."""
    txns = _load_txn_records(session)
    net, anchor = _net_by_pool(session)
    pools = [
        {"pool_id": p.pool_id, "provider": p.provider, "opening_balance": p.opening_balance,
         "current_balance": p.current_balance, "ts": anchor}
        for p in session.exec(select(Pool)).all()
    ]

    # Deterministic rule detectors (context-aware).
    findings: list[Finding] = []
    findings += detect_structuring(txns, cfg)
    findings += detect_velocity(txns, cfg, use_context=True)
    findings += detect_off_hours(txns, cfg)
    findings += detect_balance_inconsistency(pools, net, cfg)

    # Secondary IsolationForest — confidence-only nudge.
    bumps = _isolation_forest_bump(findings, txns, cfg)

    anomaly_dicts: list[dict] = []
    for i, f in enumerate(findings):
        conf = _finding_confidence(f, bumps.get(i, 0.0), data_freshness, cfg)
        anomaly_dicts.append({
            "type": "anomaly", "severity": _severity_from_confidence(conf), "label": ANOMALY_LABEL,
            "anomaly_type": f.anomaly_type, "provider": f.provider, "pool_id": f.pool_id,
            "evidence": f.evidence, "baseline": f.baseline, "observed": f.observed,
            "confidence": conf, "ts": f.ts,
            "covered_txn_ids": f.covered_txn_ids, "active_event": f.within_event,
        })

    liquidity_dicts = _forecast_liquidity_alerts(session, data_freshness, anchor)

    all_dicts = anomaly_dicts + liquidity_dicts
    all_dicts.sort(key=lambda a: a["ts"])  # stable ids in chronological order

    # Persist (idempotent: replace). Cases + their audit trail are regenerated
    # in lockstep with the alerts they mirror, so linkage stays consistent.
    from app.modules.cases.models import Case, CaseEvent
    from app.modules.cases.service import create_cases_for_alerts

    session.exec(delete(CaseEvent))
    session.exec(delete(Case))
    session.exec(delete(Alert))
    session.flush()

    persisted: list[Alert] = []
    for i, a in enumerate(all_dicts, start=1):
        alert = Alert(id=f"alert_{i:04d}", case_id=None, **a)
        session.add(alert)
        persisted.append(alert)

    # Auto-create + route one case per alert (sets each alert's case_id).
    create_cases_for_alerts(session, persisted)
    session.commit()

    return {
        "total": len(all_dicts),
        "anomaly": len(anomaly_dicts),
        "liquidity": len(liquidity_dicts),
        "by_type": {t: sum(1 for a in anomaly_dicts if a["anomaly_type"] == t)
                    for t in {a["anomaly_type"] for a in anomaly_dicts}},
    }


def ensure_alerts(session: Session) -> None:
    """Run detection lazily if the alerts table is empty but data exists."""
    has_alerts = session.exec(select(Alert)).first() is not None
    has_txns = session.exec(select(Transaction)).first() is not None
    if has_txns and not has_alerts:
        run_detection(session)


def get_active_context(session: Session) -> dict | None:
    """Response context: recognise a known event explaining current high volume."""
    _, anchor = _net_by_pool(session)
    if anchor is None:
        return None
    ev = active_event(anchor)
    if not ev:
        return None
    return {"active_event": ev, "note": f"high volume recognized as expected {ev} demand"}


def get_alerts(session: Session) -> list[Alert]:
    """All persisted alerts, ordered by ts desc (newest first)."""
    return list(session.exec(select(Alert).order_by(Alert.ts.desc())).all())
