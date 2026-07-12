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
    safety_floor: int = 0
    # at_floor | insufficient_data | intermittent | filling | projected
    projection_state: str = "projected"
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


# --------------------------------------------------------------------------- #
# Trend robustness: EMA is the base (Rule 1); "accelerating" needs a CONFIRMED
# multi-reading ramp (Rule 2) that isn't a single-transaction artefact (Rule 3).
# --------------------------------------------------------------------------- #
def _ema_reading_series(burn: np.ndarray, cfg: ForecastConfig) -> list[float]:
    """The last N EMA burn-rate readings, one per recent bucket.

    Each reading is the recency-weighted EMA computed *as of* that bucket's
    boundary, so the series shows how the base rate evolved. The final reading
    equals the current EMA burn rate (the base prediction is never altered).
    """
    b = cfg.history_bucket_minutes
    total = len(burn)
    readings: list[float] = []
    for k in range(cfg.trend_reading_count - 1, -1, -1):
        end = max(1, min(total, total - k * b))
        readings.append(_ema_last(burn[:end], cfg.ema_span))
    return readings


def _confirmed_run(
    readings: list[float], cfg: ForecastConfig, direction: int
) -> tuple[bool, int, float]:
    """Longest near-monotonic run in `direction` ending at the newest reading.

    direction: +1 for a rising ramp, -1 for a falling one. A step may counter-move
    within `trend_monotonic_tolerance` of the prior reading and still count, but the
    run is only "confirmed" when it spans >= K steps AND its cumulative signed
    magnitude clears `trend_min_cumulative_rise` (so a wiggle never qualifies).
    """
    diffs = [readings[i] - readings[i - 1] for i in range(1, len(readings))]
    run, cumulative = 0, 0.0
    for i in range(len(diffs) - 1, -1, -1):
        step = diffs[i] * direction
        tolerance = cfg.trend_monotonic_tolerance * (abs(readings[i]) + 1.0)
        if step > 0 or step >= -tolerance:
            run += 1
            cumulative += step
        else:
            break
    confirmed = (run >= cfg.trend_min_consecutive
                 and cumulative >= cfg.trend_min_cumulative_rise)
    return confirmed, run, cumulative


def _is_intermittent(
    in_window_ts: list[datetime], cfg: ForecastConfig
) -> tuple[bool, dict]:
    """Classify demand as intermittent (clumpy) vs sustained (fairly regular).

    Inter-arrival times are measured over UNIQUE timestamps — a burst of several
    transactions at the same instant is ONE arrival event, not many (this also
    keeps regularly-clocked synthetic bursts from looking clumpy). Demand is
    intermittent when the inter-arrival CV exceeds the threshold OR a single quiet
    gap spans more than `max_gap_fraction` of the window (burst → gap → burst).
    """
    times = sorted(set(in_window_ts))
    if len(times) < 2:
        # A single arrival instant can't establish regularity -> treat cautiously.
        return True, {"arrivals": len(times), "cv": None, "max_gap_fraction": None}
    gaps = [(times[i] - times[i - 1]).total_seconds() / 60.0 for i in range(1, len(times))]
    mean = float(np.mean(gaps))
    if mean <= 0:
        return True, {"arrivals": len(times), "cv": None, "max_gap_fraction": None}
    cv = float(np.std(gaps)) / mean
    max_gap_fraction = max(gaps) / cfg.analysis_window_minutes
    intermittent = cv > cfg.intermittent_cv_threshold or max_gap_fraction > cfg.max_gap_fraction
    return intermittent, {
        "arrivals": len(times),
        "cv": round(cv, 3),
        "max_gap_fraction": round(max_gap_fraction, 3),
    }


def _dominant_spike(
    effects: list[Effect], anchor: datetime, cfg: ForecastConfig
) -> dict | None:
    """If one transaction dominates the recent-window net drain, describe it.

    Returns `{amount, share}` when the largest single cash-out is >= the dominance
    threshold of the recent-window net drain (an isolated spike — evidence, not a
    confirmed trend), else None.
    """
    recent_start = anchor - timedelta(minutes=cfg.spike_recent_minutes)
    recent = [d for ts, d in effects if ts > recent_start]
    net_drain = -sum(recent)                     # positive when draining on net
    drains = [-d for d in recent if d < 0]       # per-transaction cash-out sizes
    if net_drain <= 0 or not drains:
        return None
    largest = max(drains)
    share = largest / net_drain
    if share >= cfg.spike_dominance_threshold:
        return {"amount": int(round(largest)), "share": round(share, 3)}
    return None


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
        # Named to match the frontend ConfidenceFactors contract.
        # volatility = share of confidence lost to variance (0 = steady, 1 = chaotic)
        "volatility": round(1.0 - variance_factor, 3),
        # sample_size here is the 0-1 normalized factor (not the raw count)
        "sample_size": round(sample_factor, 3),
        "data_freshness": round(data_freshness, 3),
    }
    # Return UNROUNDED — the caller may apply a low-confidence penalty first and
    # rounds exactly once, so a small confidence never collides with itself.
    return confidence, factors


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


def _recommended_action(
    pool_id: str, status: PoolStatus, trend: str, projection_state: str = "projected"
) -> str:
    """Advisory, provider-respecting, safe language. Never cross-provider."""
    label = _PROVIDER_LABELS.get(pool_id, pool_id)
    # Low-confidence watching states advise monitoring, not a premature top-up.
    if projection_state in ("insufficient_data", "intermittent"):
        if pool_id == PoolId.physical_cash.value:
            return "Activity is limited or uneven — keep monitoring physical cash levels."
        return f"Activity is limited or uneven — keep monitoring {label}."
    if status in (PoolStatus.healthy,) or trend == "filling":
        if pool_id == PoolId.physical_cash.value:
            return "Physical cash levels look stable — continue to monitor."
        return f"{label} balance looks stable — continue to monitor."
    # watch / critical
    if pool_id == PoolId.physical_cash.value:
        return "Consider arranging cash support to replenish the drawer before it runs low."
    return f"Consider topping up {label} via an approved channel before it runs low."


def _evidence(
    projection_state: str,
    pool_id: str,
    trend: str,
    ema_burn: float,
    earlier_rate: float,
    recent_rate: float,
    history: list[tuple[datetime, int]],
    sample_size: int,
    cfg: ForecastConfig,
    spike: dict | None = None,
    safety_floor: int = 0,
    near_term_none: bool = False,
) -> list[str]:
    win = cfg.analysis_window_minutes

    # --- low-confidence / at-floor states: WATCHING, never "all clear" ---
    if projection_state == "at_floor":
        ev = [f"Balance at or below the safety reserve of BDT {safety_floor:,} — needs attention now."]
        if history:
            ev.append(f"Balance moved {history[0][1]:,}→{history[-1][1]:,} BDT over last {win}m")
        ev.append(f"Based on {sample_size} transactions in the window")
        return ev

    if projection_state == "insufficient_data":
        return [
            "Limited recent activity — low-confidence, monitoring.",
            f"Only {sample_size} transaction(s) in the last {win}m",
        ]

    if projection_state == "intermittent":
        return [
            "Repeated short bursts with quiet gaps — intermittent demand, monitoring.",
            f"Net cash-out ~{_rate_str(ema_burn)} BDT/min over last {win}m",
            f"Based on {sample_size} transactions in the window",
        ]

    # --- filling / projected ---
    ev: list[str] = []
    if trend == "filling":
        ev.append(f"Net inflow ~{_rate_str(ema_burn)} BDT/min over last {win}m (filling)")
    else:
        ev.append(f"Net cash-out ~{_rate_str(ema_burn)} BDT/min over last {win}m")

    if history:
        first_b, last_b = history[0][1], history[-1][1]
        ev.append(f"Balance moved {first_b:,}→{last_b:,} BDT over last {win}m")

    # A dominant single transaction is surfaced as pending-confirmation evidence
    # (replacing the trend descriptor) — calm language, never "burn rate increased".
    if spike is not None:
        ev.append(
            f"Large withdrawal of BDT {spike['amount']:,} observed — awaiting "
            "further activity to confirm sustained demand."
        )
    elif near_term_none:
        ev.append("No near-term shortage projected at the current rate.")
    elif trend == "accelerating":
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
    window_start = anchor - timedelta(minutes=cfg.analysis_window_minutes)
    current_balance = opening_balance + sum(d for _, d in effects)

    # Everything operates over the analysis window (the memory horizon): activity
    # older than window_start has aged out and does not influence the forecast.
    in_window = [(ts, d) for ts, d in effects if ts > window_start]
    sample_size = len(in_window)

    burn = _per_minute_burn(effects, window_start, cfg)
    ema_burn = _ema_last(burn, cfg.ema_span)

    # Recent vs earlier sub-window rates — used ONLY for the accelerating
    # projection rate (how much the countdown shortens), never for the label.
    recent_minutes = max(1, int(round(cfg.analysis_window_minutes * cfg.recent_fraction)))
    earlier_minutes = max(1, cfg.analysis_window_minutes - recent_minutes)
    earlier_rate = float(burn[:earlier_minutes].sum()) / earlier_minutes
    recent_rate = float(burn[earlier_minutes:].sum()) / recent_minutes

    headroom = current_balance - safety_floor

    # --------------------------------------------------------- projection state
    # Decide WHAT can be honestly stated before assigning any countdown. Too
    # little / uneven data stays low-confidence AND WATCHING — never "all clear",
    # never a fake precise countdown.
    spike: dict | None = None
    minutes_to_depletion: float | None = None
    projected_ts: datetime | None = None
    projection_rate = ema_burn

    if headroom <= 0:
        # Rule 5: already at/below the safety reserve — a REAL at-floor state now,
        # surfaced directly rather than routed through the rate model.
        projection_state = "at_floor"
        trend = "steady"
        minutes_to_depletion = 0.0
        projected_ts = anchor
    elif sample_size < cfg.min_txns_for_projection:
        projection_state = "insufficient_data"       # watching, low-confidence
        trend = "steady"
    elif ema_burn <= 0:
        projection_state = "filling"                  # safe: net inflow
        trend = "filling"
    elif _is_intermittent([ts for ts, _ in in_window], cfg)[0]:
        projection_state = "intermittent"            # clumpy bursts: watching
        trend = "steady"
    else:
        projection_state = "projected"
        readings = _ema_reading_series(burn, cfg)
        spike = _dominant_spike(effects, anchor, cfg)                 # Rule 3
        accel_confirmed, _, _ = _confirmed_run(readings, cfg, +1)     # Rule 2
        ease_confirmed, _, _ = _confirmed_run(readings, cfg, -1)

        if spike is not None:
            trend = "steady"           # Rule 3 precedence: a lone spike never accelerates
        elif accel_confirmed:
            trend = "accelerating"
        elif ease_confirmed:
            trend = "easing"
        else:
            trend = "steady"

        # Accelerating shortens via the higher recent rate (never below the EMA);
        # every other trend keeps the EMA base, so a lone spike cannot shorten it.
        projection_rate = max(recent_rate, ema_burn) if trend == "accelerating" else ema_burn

        # Rule 4: rate stability + horizon. Floor the rate before dividing, and
        # cap absurd countdowns as "no near-term shortage" (null) rather than a
        # falsely-precise raw number.
        if projection_rate > cfg.rate_epsilon:
            mtd = headroom / projection_rate
            if mtd <= cfg.max_horizon_minutes:
                minutes_to_depletion = mtd
                projected_ts = anchor + timedelta(minutes=mtd)

    near_term_none = projection_state == "projected" and minutes_to_depletion is None

    # ---------------------------------------------------------------- status
    if projection_state == "at_floor":
        status = PoolStatus.critical
    elif projection_state in ("insufficient_data", "intermittent"):
        status = PoolStatus.watch    # WATCHING — low-confidence, never "all clear"
    else:  # filling / projected
        status = status_from_minutes(minutes_to_depletion, trend, cfg)

    confidence, factors = _confidence(burn, ema_burn, sample_size, data_freshness, cfg)
    if projection_state in ("insufficient_data", "intermittent"):
        confidence *= cfg.low_confidence_penalty
    confidence = round(confidence, 2)   # round exactly once (no double-rounding)

    history = _balance_history(effects, opening_balance, window_start, anchor, cfg)
    evidence = _evidence(projection_state, pool_id, trend, ema_burn, earlier_rate,
                         recent_rate, history, sample_size, cfg, spike=spike,
                         safety_floor=safety_floor, near_term_none=near_term_none)
    action = _recommended_action(pool_id, status, trend, projection_state)

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
        safety_floor=int(safety_floor),
        projection_state=projection_state,
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
    freshness_by_pool: dict[str, float] | None = None,
) -> list[ForecastResult]:
    """Compute forecasts for all pools, anchored to the latest observed activity.

    `freshness_by_pool` (Phase 5) lets a broken feed degrade only its own pool's
    confidence: a per-pool override of `data_freshness` (falls back to the scalar
    for any pool not listed). Fresh feeds keep `data_freshness == 1.0`.
    """
    pools = session.exec(select(Pool)).all()
    effects_by_pool, anchor = _pool_effects_from_db(session)
    if anchor is None:
        anchor = datetime.utcnow()

    results: list[ForecastResult] = []
    for pool in pools:
        pool_freshness = (
            freshness_by_pool.get(pool.pool_id, data_freshness)
            if freshness_by_pool else data_freshness
        )
        results.append(
            forecast_pool(
                pool_id=pool.pool_id,
                effects=effects_by_pool.get(pool.pool_id, []),
                opening_balance=pool.opening_balance,
                anchor=anchor,
                safety_floor=safety_floor_for(pool.pool_id),
                data_freshness=pool_freshness,
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
