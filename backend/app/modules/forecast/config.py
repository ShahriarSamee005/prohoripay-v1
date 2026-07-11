"""Tunable constants for the deterministic liquidity-forecast engine.

Everything the engine's behaviour depends on lives here: window sizes, the EMA
span, trend sensitivity, per-pool safety floors, confidence shaping, and the
minutes-to-depletion status thresholds. No wall-clock or randomness — the engine
is fully reproducible from these constants plus the transaction data.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import PoolId


@dataclass(frozen=True)
class ForecastConfig:
    """All knobs for one forecast computation (overridable in tests)."""

    # Recent window (minutes) over which flow rates are measured.
    window_minutes: int = 45
    # EMA span (in per-minute buckets) — recency weighting for the net burn rate.
    ema_span: int = 10

    # Fraction of the window treated as the "recent" sub-window for trend.
    recent_fraction: float = 0.5
    # recent_rate > earlier_rate * accel_ratio  => "accelerating".
    accel_ratio: float = 1.20
    # recent_rate < earlier_rate * ease_ratio    => "easing".
    ease_ratio: float = 0.80

    # Confidence: sample saturation constant. sample_factor = n / (n + k).
    sample_k: float = 8.0

    # Balance history for the burn-down chart: one point every N minutes.
    history_bucket_minutes: int = 5

    # Minutes-to-depletion status thresholds (single source of truth for status).
    critical_minutes: float = 30.0
    watch_minutes: float = 90.0


DEFAULT_CONFIG = ForecastConfig()

# Per-pool safety floor (BDT): the operational reserve you never want to cross,
# NOT zero. Depletion is measured to this floor, not to an empty pool.
SAFETY_FLOORS: dict[str, int] = {
    PoolId.physical_cash.value: 20_000,
    PoolId.bkash.value: 10_000,
    PoolId.nagad.value: 10_000,
    PoolId.rocket.value: 10_000,
}
DEFAULT_SAFETY_FLOOR: int = 10_000


def safety_floor_for(pool_id: str) -> int:
    return SAFETY_FLOORS.get(pool_id, DEFAULT_SAFETY_FLOOR)
