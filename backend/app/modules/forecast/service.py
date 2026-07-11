"""Deterministic liquidity-forecast engine (pandas / numpy — NO LLM).

Per pool, independently, from the signed `pool_effects` of recent transactions:

  * net burn rate  — a recency-weighted EMA of net signed flow per minute over a
    recent window. Positive = draining, negative = filling.
  * trend          — split the window into an earlier and a more-recent half and
    compare their net rates: accelerating / easing / steady (or filling).
  * minutes_to_depletion — (current_balance - safety_floor) / projection_rate,
    or None when the pool is filling / not depleting.
  * status         — bucketed from minutes_to_depletion. THE single source of
    truth for pool status (imported by the pools endpoint).
  * confidence     — earned in [0,1]; see `_confidence` for the documented formula.
  * evidence / recommended_action / history — advisory, provider-respecting,
    safe language, plus a bucketed balance series for the burn-down chart.

The heavy lifting is the pure function `forecast_pool`, which takes plain data
(no DB), so it is trivially unit-testable and reusable by the lead-time replay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlmodel import Session, select

from app.core.enums import PoolId, PoolStatus
from app.core.models import Pool, Transaction
from app.modules.forecast.config import (
    DEFAULT_CONFIG,
    ForecastConfig,
    safety_floor_for,
)

# A single pool effect as (timestamp, signed delta).
Effect = tuple[datetime, int]

_PROVIDER_LABELS = {"physical_cash": "Physical cash", "bkash": "bKash",
                    "nagad": "Nagad", "rocket": "Rocket"}


@dataclass
class ForecastResult:
    """Full deterministic forecast for one pool."""

    pool_id: str
    current_balance: int
    burn_rate_per_min: int          # signed projection rate (positive = draining)
    ema_burn_rate: float            # recency-weighted net burn (headline rate)
    projection_rate: float          # rate actually used for the countdown
    minutes_to_depletion: float | None
    projected_depletion_ts: datetime | None
    trend: str                      # accelerating | easing | steady | filling
    status: PoolStatus
    confidence: float
    confidence_factors: dict = field(default_factory=dict)
    recommended_action: str = ""
    evidence: list[str] = field(default_factory=list)
    history: list[tuple[datetime, int]] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Status — the single source of truth (imported by the pools endpoint).
# --------------------------------------------------------------------------- #
def status_from_minutes(
    minutes_to_depletion: float | None,
    trend: str,
    cfg: ForecastConfig = DEFAULT_CONFIG,
) -> PoolStatus:
    """Bucket a minutes-to-depletion value into a pool status.

    Filling / non-depleting pools are healthy. Otherwise: sooner depletion =>
    more severe status.
    """
    if trend == "filling" or minutes_to_depletion is None:
        return PoolStatus.healthy
    if minutes_to_depletion < cfg.critical_minutes:
        return PoolStatus.critical
    if minutes_to_depletion < cfg.watch_minutes:
        return PoolStatus.watch
    return PoolStatus.healthy


# --------------------------------------------------------------------------- #
# Internals.
# --------------------------------------------------------------------------- #
def _per_minute_burn(effects: list[Effect], window_start: datetime, cfg: ForecastConfig) -> np.ndarray:
    """Net *burn* per minute over the window (burn = -netflow; +ve = draining)."""
    burn = np.zeros(cfg.window_minutes, dtype=float)
    for ts, delta in effects:
        offset = (ts - window_start).total_seconds() / 60.0
        if offset < 0:
            continue
        idx = min(cfg.window_minutes - 1, int(offset))
        burn[idx] += -float(delta)  # draining (delta<0) contributes positive burn
    return burn


def _ema_last(series: np.ndarray, span: int) -> float:
    """Recency-weighted EMA; return the most recent value (adjust=False)."""
    return float(pd.Series(series).ewm(span=span, adjust=False).mean().iloc[-1])


def _bucket_rates(burn: np.ndarray, cfg: ForecastConfig) -> np.ndarray:
    """Net burn rate (per minute) within each fixed-size time bucket.

    Bucketing (default 5-min) before measuring variance removes the zero-inflation
    of raw per-minute counts (transaction discreteness) so the variance reflects
    genuine *rate* instability, not just how bursty individual minutes are.
    """
    b = cfg.history_bucket_minutes
    n_buckets = max(1, len(burn) // b)
    rates = np.empty(n_buckets, dtype=float)
    for i in range(n_buckets):
        chunk = burn[i * b:(i + 1) * b]
        rates[i] = chunk.sum() / max(1, len(chunk))
    return rates


def _confidence(
    burn: np.ndarray,
    ema_burn: float,
    sample_size: int,
    data_freshness: float,
    cfg: ForecastConfig,
) -> tuple[float, dict]:
    """Earned confidence in [0,1].

    confidence = variance_factor * sample_factor * data_freshness

      * variance_factor = 1 / (1 + cv), where cv = std(bucketed rates) /
        (|mean(bucketed rates)| + 1). A steady draining rate across the window ->
        cv ~ 0 -> ~1; a rate that lurches around -> lower.
      * sample_factor  = n / (n + k). More transactions in the window -> higher
        confidence, saturating toward 1 (k from config).
      * data_freshness = meta.confidence_modifier. Stale/degraded feeds (<1)
        multiply confidence down (Scenario C).
    """
    bucket_rates = _bucket_rates(burn, cfg)
    std = float(np.std(bucket_rates))
    scale = abs(float(np.mean(bucket_rates))) + 1.0
    cv = std / scale
    variance_factor = 1.0 / (1.0 + cv)
    sample_factor = sample_size / (sample_size + cfg.sample_k) if sample_size > 0 else 0.0
    confidence = variance_factor * sample_factor * data_freshness
    confidence = max(0.0, min(1.0, confidence))
    factors = {
        "variance_factor": round(variance_factor, 3),
        "sample_factor": round(sample_factor, 3),
        "data_freshness": round(data_freshness, 3),
        "sample_size": int(sample_size),
        "coefficient_of_variation": round(cv, 3),
    }
    return round(confidence, 2), factors


def _balance_history(
    effects: list[Effect],
    opening_balance: int,
    window_start: datetime,
    anchor: datetime,
    cfg: ForecastConfig,
) -> list[tuple[datetime, int]]:
    """Bucketed balance series across the window (for the burn-down chart)."""
    if not effects:
        return [(window_start, opening_balance), (anchor, opening_balance)]

    ts_sorted = sorted(effects, key=lambda e: e[0])
    times = np.array([e[0].timestamp() for e in ts_sorted])
    cum = np.cumsum([e[1] for e in ts_sorted])

    points: list[tuple[datetime, int]] = []
    step = timedelta(minutes=cfg.history_bucket_minutes)
    t = window_start
    while t < anchor:
        idx = int(np.searchsorted(times, t.timestamp(), side="right"))
        balance = opening_balance + (int(cum[idx - 1]) if idx > 0 else 0)
        points.append((t, balance))
        t += step
    # Always finish exactly at the anchor with the current balance.
    points.append((anchor, opening_balance + int(cum[-1])))
    return points


def _rate_str(rate: float) -> str:
    return f"{abs(round(rate)):,}"


def _recommended_action(pool_id: str, status: PoolStatus, trend: str) -> str:
    """Advisory, provider-respecting, safe language. Never cross-provider."""
    label = _PROVIDER_LABELS.get(pool_id, pool_id)
    if status in (PoolStatus.healthy,) or trend == "filling":
        if pool_id == PoolId.physical_cash.value:
            return "Physical cash levels look stable — continue to monitor."
        return f"{label} balance looks stable — continue to monitor."
    # watch / critical
    if pool_id == PoolId.physical_cash.value:
        return "Consider arranging cash support to replenish the drawer before it runs low."
    return f"Consider topping up {label} via an approved channel before it runs low."


def _evidence(
    pool_id: str,
    trend: str,
    ema_burn: float,
    earlier_rate: float,
    recent_rate: float,
    history: list[tuple[datetime, int]],
    sample_size: int,
    cfg: ForecastConfig,
) -> list[str]:
    ev: list[str] = []
    if trend == "filling":
        ev.append(f"Net inflow ~{_rate_str(ema_burn)} BDT/min over last {cfg.window_minutes}m (filling)")
    else:
        ev.append(f"Net cash-out ~{_rate_str(ema_burn)} BDT/min over last {cfg.window_minutes}m")

    if history:
        first_b, last_b = history[0][1], history[-1][1]
        ev.append(f"Balance moved {first_b:,}→{last_b:,} BDT over last {cfg.window_minutes}m")

    if trend == "accelerating":
        ev.append(f"Draining is accelerating (recent ~{_rate_str(recent_rate)} vs earlier ~{_rate_str(earlier_rate)} BDT/min)")
    elif trend == "easing":
        ev.append(f"Draining is easing (recent ~{_rate_str(recent_rate)} vs earlier ~{_rate_str(earlier_rate)} BDT/min)")
    elif trend == "steady":
        ev.append(f"Draining is steady (~{_rate_str(ema_burn)} BDT/min)")
    else:  # filling
        ev.append("Pool is filling, not depleting")

    ev.append(f"Based on {sample_size} transactions in the window")
    return ev


# --------------------------------------------------------------------------- #
# The pure engine.
# --------------------------------------------------------------------------- #
def forecast_pool(
    pool_id: str,
    effects: list[Effect],
    opening_balance: int,
    anchor: datetime,
    safety_floor: int,
    data_freshness: float = 1.0,
    cfg: ForecastConfig = DEFAULT_CONFIG,
) -> ForecastResult:
    """Compute a full forecast for one pool from its signed effects.

    Args:
        effects: (ts, delta) for THIS pool, for all transactions up to `anchor`.
        opening_balance: pool balance before any transaction.
        anchor: the "now" the forecast is computed as-of (latest observed data).
        safety_floor: operational reserve; depletion is measured to this, not 0.
        data_freshness: meta.confidence_modifier (1.0 when data is fresh).
    """
    window_start = anchor - timedelta(minutes=cfg.window_minutes)
    current_balance = opening_balance + sum(d for _, d in effects)

    in_window = [(ts, d) for ts, d in effects if ts > window_start]
    sample_size = len(in_window)

    burn = _per_minute_burn(effects, window_start, cfg)
    ema_burn = _ema_last(burn, cfg.ema_span)

    # Trend via earlier vs recent sub-windows.
    recent_minutes = max(1, int(round(cfg.window_minutes * cfg.recent_fraction)))
    earlier_minutes = max(1, cfg.window_minutes - recent_minutes)
    earlier_rate = float(burn[:earlier_minutes].sum()) / earlier_minutes
    recent_rate = float(burn[earlier_minutes:].sum()) / recent_minutes

    if ema_burn <= 0:
        trend = "filling"
        projection_rate = ema_burn  # negative / zero
    else:
        if earlier_rate <= 0:
            # Draining only started recently -> clearly accelerating.
            trend = "accelerating" if recent_rate > 0 else "steady"
        elif recent_rate > earlier_rate * cfg.accel_ratio:
            trend = "accelerating"
        elif recent_rate < earlier_rate * cfg.ease_ratio:
            trend = "easing"
        else:
            trend = "steady"
        # Accelerating projects with the higher recent rate (countdown shortens),
        # but never slower than the EMA. Otherwise project with the EMA.
        projection_rate = max(recent_rate, ema_burn) if trend == "accelerating" else ema_burn

    # Minutes to depletion (to the safety floor, not to zero).
    headroom = current_balance - safety_floor
    if trend == "filling" or projection_rate <= 0:
        minutes_to_depletion: float | None = None
        projected_ts: datetime | None = None
    elif headroom <= 0:
        minutes_to_depletion = 0.0
        projected_ts = anchor
    else:
        minutes_to_depletion = headroom / projection_rate
        projected_ts = anchor + timedelta(minutes=minutes_to_depletion)

    status = status_from_minutes(minutes_to_depletion, trend, cfg)
    confidence, factors = _confidence(burn, ema_burn, sample_size, data_freshness, cfg)
    history = _balance_history(effects, opening_balance, window_start, anchor, cfg)
    evidence = _evidence(pool_id, trend, ema_burn, earlier_rate, recent_rate,
                         history, sample_size, cfg)
    action = _recommended_action(pool_id, status, trend)

    return ForecastResult(
        pool_id=pool_id,
        current_balance=int(current_balance),
        burn_rate_per_min=int(round(projection_rate)),
        ema_burn_rate=round(ema_burn, 2),
        projection_rate=round(projection_rate, 2),
        minutes_to_depletion=(round(minutes_to_depletion, 1)
                              if minutes_to_depletion is not None else None),
        projected_depletion_ts=projected_ts,
        trend=trend,
        status=status,
        confidence=confidence,
        confidence_factors=factors,
        recommended_action=action,
        evidence=evidence,
        history=history,
    )


# --------------------------------------------------------------------------- #
# DB-facing helpers.
# --------------------------------------------------------------------------- #
def _pool_effects_from_db(session: Session) -> tuple[dict[str, list[Effect]], datetime | None]:
    """Extract per-pool (ts, delta) effect lists and the latest activity time."""
    txns = session.exec(select(Transaction)).all()
    by_pool: dict[str, list[Effect]] = {}
    anchor: datetime | None = None
    for t in txns:
        anchor = t.ts if anchor is None or t.ts > anchor else anchor
        for eff in t.pool_effects:
            by_pool.setdefault(eff["pool_id"], []).append((t.ts, int(eff["delta"])))
    return by_pool, anchor


# Stable display order: shared physical cash first, then providers.
_POOL_ORDER = {PoolId.physical_cash.value: 0, PoolId.bkash.value: 1,
               PoolId.nagad.value: 2, PoolId.rocket.value: 3}


def compute_forecasts(
    session: Session,
    data_freshness: float = 1.0,
    cfg: ForecastConfig = DEFAULT_CONFIG,
) -> list[ForecastResult]:
    """Compute forecasts for all pools, anchored to the latest observed activity."""
    pools = session.exec(select(Pool)).all()
    effects_by_pool, anchor = _pool_effects_from_db(session)
    if anchor is None:
        anchor = datetime.utcnow()

    results: list[ForecastResult] = []
    for pool in pools:
        results.append(
            forecast_pool(
                pool_id=pool.pool_id,
                effects=effects_by_pool.get(pool.pool_id, []),
                opening_balance=pool.opening_balance,
                anchor=anchor,
                safety_floor=safety_floor_for(pool.pool_id),
                data_freshness=data_freshness,
                cfg=cfg,
            )
        )
    results.sort(key=lambda r: _POOL_ORDER.get(r.pool_id, 99))
    return results


def pool_status_map(
    session: Session,
    data_freshness: float = 1.0,
    cfg: ForecastConfig = DEFAULT_CONFIG,
) -> dict[str, PoolStatus]:
    """pool_id -> forecast-derived status. Used by /api/pools so the two agree."""
    return {r.pool_id: r.status for r in compute_forecasts(session, data_freshness, cfg)}
