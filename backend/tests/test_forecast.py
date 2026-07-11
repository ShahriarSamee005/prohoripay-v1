"""Unit tests for the deterministic forecast engine (pure `forecast_pool`)."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.modules.forecast.config import ForecastConfig
from app.modules.forecast.service import forecast_pool

ANCHOR = datetime(2026, 7, 11, 12, 0, 0)
CFG = ForecastConfig()  # defaults: window 45, ema_span 10, thresholds 30/90


def _effects(mag_fn, sign: int = -1, cfg: ForecastConfig = CFG):
    """One effect per minute across the window; delta = sign * mag_fn(minute)."""
    ws = ANCHOR - timedelta(minutes=cfg.window_minutes)
    return [(ws + timedelta(minutes=i + 0.5), sign * mag_fn(i)) for i in range(cfg.window_minutes)]


# --------------------------------------------------------------- known-case math
def test_known_case_watch():
    """Constant 1000/min drain, 50k headroom -> ~50 min -> watch."""
    effects = _effects(lambda i: 1000)          # draining (sign -1)
    total = -1000 * CFG.window_minutes
    current = 60_000
    opening = current - total
    r = forecast_pool("physical_cash", effects, opening, ANCHOR, safety_floor=10_000, cfg=CFG)

    assert r.current_balance == current
    assert abs(r.ema_burn_rate - 1000) < 10        # steady EMA of a constant series
    assert r.trend == "steady"
    assert abs(r.minutes_to_depletion - 50.0) < 1.0   # (60000-10000)/1000
    assert r.status.value == "watch"


def test_known_case_critical():
    """Same rate, only 10k headroom -> ~10 min -> critical."""
    effects = _effects(lambda i: 1000)
    total = -1000 * CFG.window_minutes
    current = 20_000
    opening = current - total
    r = forecast_pool("physical_cash", effects, opening, ANCHOR, safety_floor=10_000, cfg=CFG)

    assert abs(r.minutes_to_depletion - 10.0) < 0.6
    assert r.status.value == "critical"
    # Countdown reconciles with the reported rate.
    headroom = r.current_balance - 10_000
    assert abs(headroom / r.burn_rate_per_min - r.minutes_to_depletion) < 0.6


# ------------------------------------------------------------------- filling pool
def test_filling_pool_has_null_countdown():
    """A pool gaining balance never depletes: null countdown, trend 'filling'."""
    effects = _effects(lambda i: 1000, sign=+1)   # filling (delta > 0)
    r = forecast_pool("bkash", effects, opening_balance=50_000, anchor=ANCHOR,
                      safety_floor=10_000, cfg=CFG)

    assert r.ema_burn_rate < 0                     # net inflow
    assert r.trend == "filling"
    assert r.minutes_to_depletion is None          # never negative
    assert r.projected_depletion_ts is None
    assert r.status.value == "healthy"


# ------------------------------------------------------------------------- trend
def test_accelerating_labeled_and_shortens_countdown():
    """A late-accelerating drain is 'accelerating' and beats the flat-EMA estimate."""
    # earlier 23 min @ 500/min, recent 22 min @ 2000/min.
    effects = _effects(lambda i: 500 if i < 23 else 2000)
    total = -(500 * 23 + 2000 * 22)
    current = 100_000
    opening = current - total
    r = forecast_pool("physical_cash", effects, opening, ANCHOR, safety_floor=10_000, cfg=CFG)

    assert r.trend == "accelerating"
    # Projecting with the higher recent rate yields a SHORTER countdown than the
    # flat EMA-only estimate would.
    headroom = r.current_balance - 10_000
    flat_ema_estimate = headroom / r.ema_burn_rate
    assert r.minutes_to_depletion < flat_ema_estimate


# -------------------------------------------------------------------- confidence
def test_steady_series_more_confident_than_volatile():
    steady = _effects(lambda i: 1000)
    volatile = _effects(lambda i: 2000 if (i // CFG.history_bucket_minutes) % 2 == 0 else 100)

    rs = forecast_pool("bkash", steady, 100_000, ANCHOR, 10_000, cfg=CFG)
    rv = forecast_pool("bkash", volatile, 100_000, ANCHOR, 10_000, cfg=CFG)

    assert rs.confidence > rv.confidence


def test_stale_meta_lowers_confidence():
    steady = _effects(lambda i: 1000)
    fresh = forecast_pool("bkash", steady, 100_000, ANCHOR, 10_000, data_freshness=1.0, cfg=CFG)
    stale = forecast_pool("bkash", steady, 100_000, ANCHOR, 10_000, data_freshness=0.5, cfg=CFG)

    assert stale.confidence < fresh.confidence
    assert abs(stale.confidence - fresh.confidence * 0.5) < 0.02   # ~halved (data freshness)
