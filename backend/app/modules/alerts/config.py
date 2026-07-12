"""Tunable constants for deterministic, context-aware anomaly + liquidity detection.

No static volume threshold governs anomalies: the context calendar raises the
baseline during known events so a legitimate Eid surge reads as expected demand.
Everything a detector depends on lives here for reproducibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.enums import PoolStatus


# --------------------------------------------------------------- context calendar
@dataclass(frozen=True)
class EventWindow:
    """A known-demand event on the reference day (seconds from midnight)."""

    name: str
    start_sec: int
    end_sec: int


# The seeded eid rush runs 10:00–12:00. A salary-day window is declared for
# completeness (no seeded salary traffic, but the calendar is data-driven-ready).
EVENT_CALENDAR: tuple[EventWindow, ...] = (
    EventWindow("eid_rush", 10 * 3600, 12 * 3600),
    EventWindow("salary_day", 7 * 3600, 9 * 3600),
)


@dataclass(frozen=True)
class DetectorConfig:
    """All detector thresholds (overridable in tests)."""

    # --- structuring: near-identical amounts, few accounts, short window ---
    struct_amount_rel: float = 0.05        # amounts within ±5% count as "identical"
    struct_min_count: int = 6
    struct_max_accounts: int = 5
    struct_window_minutes: float = 90.0

    # --- velocity spike: rate far above the (event-adjusted) baseline ---
    velocity_window_minutes: float = 5.0
    velocity_min_count: int = 8            # primary gate — normal Eid never reaches this
    velocity_factor: float = 4.0           # observed_rate >= eff_baseline*factor -> spike
    velocity_event_multiplier: float = 2.0  # raise the baseline during a known event
    velocity_min_baseline_rate: float = 0.05   # per-minute floor so baseline!=0
    velocity_max_accounts: int = 6         # concentration adds evidence/confidence

    # --- time-aware off-hours burst: rate >> expected for this hour, no known event ---
    # Intraday multipliers: hour -> expected volume relative to peak (1.0).
    # Mirrors HOUR_MULTIPLIERS in synth/config so the detector uses the same profile.
    hour_multipliers: dict = field(default_factory=lambda: {
        0: 0.03, 1: 0.02, 2: 0.02, 3: 0.02, 4: 0.02, 5: 0.05,
        6: 0.15, 7: 0.40, 8: 0.70, 9: 0.90, 10: 1.00, 11: 1.00,
        12: 0.90, 13: 0.85, 14: 0.80, 15: 0.75, 16: 0.70, 17: 0.65,
        18: 0.60, 19: 0.50, 20: 0.35, 21: 0.25, 22: 0.15, 23: 0.08,
    })
    # Expected txn/min per provider at the PEAK hour (multiplier = 1.0).
    off_hours_base_rate: float = 0.20
    # Flag when observed rate exceeds expected * this factor for that hour.
    off_hours_relative_threshold: float = 8.0
    # Legacy fields — kept for backward compat; detection logic now uses multipliers.
    quiet_start_hour: int = 0
    quiet_end_hour: int = 6                 # quiet window [00:00, 06:00)
    off_hours_min_count: int = 5
    off_hours_window_minutes: float = 60.0

    # --- balance inconsistency: stored vs recomputed balance (data quality) ---
    balance_tolerance: int = 1

    # --- context-aware volume gate (the false-positive control) ---
    volume_surge_factor: float = 2.0       # naive: observed >= baseline*this -> "review"
    event_rate_multiplier: float = 6.0     # during an event, demand up to this x baseline is expected

    # --- confidence shaping ---
    context_penalty_for_volume: float = 0.95   # mild uncertainty for in-event volume signals

    # --- IsolationForest (secondary; confidence-only, never sole justification) ---
    isolation_forest_enabled: bool = True
    isolation_forest_contamination: float = 0.12
    isolation_forest_random_state: int = 0
    isolation_forest_confidence_bump: float = 0.05


DEFAULT_DETECTOR_CONFIG = DetectorConfig()

# Liquidity alerts: which forecast statuses raise an alert. Watch is included so
# the current hidden-shortage (physical cash = watch) surfaces as an alert.
LIQUIDITY_ALERT_STATUSES: set[PoolStatus] = {PoolStatus.critical, PoolStatus.watch}

# Cluster-overlap fraction for precision/recall matching against ground truth.
MATCH_FRACTION: float = 0.5

# Safe-language labels (contract).
ANOMALY_LABEL: str = "unusual — requires review"
LIQUIDITY_LABEL: str = "liquidity pressure — requires attention"

# Banned words anywhere in alert text (compliance is scored).
BANNED_WORDS: tuple[str, ...] = ("fraud", "suspicious", "criminal", "blocking", "block ")
