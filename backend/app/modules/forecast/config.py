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

    # ANALYSIS WINDOW = MEMORY HORIZON.
    # This is the single most important knob: the longest gap the forecast will
    # bridge. ALL rate, trend, inter-arrival and confidence logic operates over
    # exactly this window. Activity separated by MORE than this many minutes is
    # treated as INDEPENDENT — an older cluster more than `analysis_window_minutes`
    # before "now" has aged out of memory and does not influence the current rate.
    analysis_window_minutes: int = 30
    # EMA span (in per-minute buckets) — recency weighting for the net burn rate.
    ema_span: int = 10

    # Fraction of the window treated as the "recent" sub-window. Used ONLY for the
    # accelerating projection rate (the countdown), not for the trend LABEL —
    # the label is gated by the confirmed-ramp logic below.
    recent_fraction: float = 0.5
    # Legacy two-sub-window ratios (kept for the accelerating projection rate).
    accel_ratio: float = 1.20
    ease_ratio: float = 0.80

    # --- trend confirmation: escalate to "accelerating" only on a CONFIRMED ramp ---
    # Number of recent EMA burn-rate readings examined (one per recent bucket).
    trend_reading_count: int = 5              # N
    # Consecutive near-monotonic steps required to confirm a ramp.
    trend_min_consecutive: int = 3            # K rising (or falling) steps
    # Minimum cumulative rise (BDT/min) across the confirming steps — not a wiggle.
    trend_min_cumulative_rise: float = 400.0
    # Near-monotonic tolerance: a step may counter-move by this fraction of the
    # prior reading and still count toward the run (small wiggles don't break it).
    trend_monotonic_tolerance: float = 0.10

    # --- single-transaction dominance guard: an isolated spike is EVIDENCE ---
    # Recent window (minutes) over which the dominant-transaction share is measured.
    spike_recent_minutes: int = 15
    # If the largest single transaction is >= this share of the recent-window net
    # drain, the jump is unconfirmed: it must NOT drive "accelerating" and must NOT
    # shorten the countdown — it is surfaced as pending-confirmation evidence.
    spike_dominance_threshold: float = 0.65

    # Confidence: sample saturation constant. sample_factor = n / (n + k).
    sample_k: float = 8.0

    # Balance history for the burn-down chart: one point every N minutes.
    history_bucket_minutes: int = 5

    # Minutes-to-depletion status thresholds (single source of truth for status).
    critical_minutes: float = 30.0
    watch_minutes: float = 90.0

    # --- projection state: sustained vs intermittent vs too-little data ---------
    # Minimum transactions in the window before ANY countdown is projected. Below
    # this we stay low-confidence and WATCHING (never "all clear").
    min_txns_for_projection: int = 3
    # Coefficient of variation (std/mean) of inter-arrival times above which demand
    # is "intermittent". A superposition of Poisson-like cash_in/cash_out streams
    # (plus a normal burst) runs at CV ~1-1.5, so this gate sits well above 1.0 to
    # avoid flagging continuous, variable-rate demand. The reliable intermittency
    # signal is a genuine QUIET gap (max_gap_fraction below); this CV gate is only
    # a backstop for extreme clumping that has no single dominant gap.
    intermittent_cv_threshold: float = 2.0
    # A single quiet gap wider than this fraction of the window => intermittent.
    # This is the primary "bursts separated by calm" detector.
    max_gap_fraction: float = 0.5
    # Multiplicative penalty applied to confidence in low-confidence states
    # (insufficient_data / intermittent) so they read as tentative, not certain.
    low_confidence_penalty: float = 0.5

    # --- rate stability / horizon (divide-by-zero + absurd countdowns) ----------
    # Floor the projection rate (BDT/min) before dividing; at/below this the pool
    # is treated as not depleting (null countdown) rather than dividing by ~zero.
    rate_epsilon: float = 1.0
    # Countdowns beyond this many minutes are reported as "no near-term shortage"
    # (null countdown) instead of an inflated, falsely-precise raw number.
    max_horizon_minutes: float = 1440.0

    @property
    def window_minutes(self) -> int:
        """Backwards-compatible alias for `analysis_window_minutes`.

        The window and the memory horizon are one and the same; existing rate /
        EMA / history code refers to it as the window.
        """
        return self.analysis_window_minutes


DEFAULT_CONFIG = ForecastConfig()

# The documented memory-horizon default, exposed at module scope for reference.
ANALYSIS_WINDOW_MINUTES: int = DEFAULT_CONFIG.analysis_window_minutes

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
