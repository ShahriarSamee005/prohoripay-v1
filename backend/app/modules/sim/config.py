"""Tunable constants for the simulation clock (deterministic — fixed seed).

A fixed seed + fixed per-tick sim-time step make any control sequence reproduce
the same demo. Nothing here is a wall-clock read inside the tick math, so replays
are exact.
"""

from __future__ import annotations

from datetime import datetime

# Reproducibility for the sim's own synthetic traffic (independent of the seed
# generator's SEED so live traffic never collides with the seeded history).
SIM_SEED: int = 7

# The sim starts where the seeded history ends (Eid rush just finished at 12:00).
SIM_START: datetime = datetime(2026, 7, 11, 12, 0, 0)

# Each tick advances synthetic time by this many minutes. Chosen so the case SLAs
# (liquidity 15m / anomaly 30m) and the forecast window (45m) are crossed within a
# small, bounded number of ticks.
SIM_MINUTES_PER_TICK: int = 5

# Default clock speed (ticks per real second) when start() gets no override.
DEFAULT_SPEED: float = 2.0

# SSE keep-alive comment cadence (seconds) when no event is pending.
KEEPALIVE_SECONDS: float = 15.0

# --- baseline (calm) per-tick traffic ---------------------------------------
# A gentle net cash-IN so that, once the clock is running, physical cash sits
# stably healthy (the seeded Scenario-A pressure eases) — until a presenter fires
# eid_rush, which then clearly drives it into a fresh liquidity alert. Amounts are
# small and volume low (below velocity_min_count) so calm traffic never self-flags.
BASELINE_COUNT: int = 3                 # kept below velocity_min_count (8)
BASELINE_CASHOUT_SHARE: float = 0.35    # majority cash_in refills physical cash
BASELINE_CASHOUT_AMOUNT: tuple[int, int] = (500, 3_000)
BASELINE_CASHIN_AMOUNT: tuple[int, int] = (500, 3_000)
BASELINE_ACCOUNT_MIN: int = 1_000
BASELINE_ACCOUNT_MAX: int = 1_400

# --- eid_rush: sustained cash-out pressure (drains physical cash) ------------
EID_RUSH_TICKS: int = 6                  # how many ticks the surge lasts
EID_INTENSITY_COUNT: dict[str, int] = {"low": 4, "medium": 8, "high": 12}
EID_CASHOUT_AMOUNT: tuple[int, int] = (3_000, 9_000)
# Cash-out spread across e-money providers (every cash_out drains physical cash).
PROVIDER_WEIGHTS: dict[str, float] = {"bkash": 0.45, "rocket": 0.35, "nagad": 0.20}

# --- inject_anomaly: a labeled cluster detection catches next tick ----------
# One preset per anomaly type. Fresh 7xxx accounts so injected clusters never
# overlap the seeded 9xxx clusters or the 1xxx normal traffic.
INJECT_PRESETS: dict[str, dict] = {
    "structuring": {
        "count": 8, "amount": (4_910, 4_990),
        "accounts": ("ACC_7001", "ACC_7002"),
    },
    "velocity_spike": {
        "count": 14, "amount": (1_000, 3_000),
        "accounts": ("ACC_7101", "ACC_7102"),
    },
    "off_hours_burst": {
        "count": 7, "amount": (2_000, 4_000),
        "accounts": ("ACC_7201", "ACC_7202"),
    },
}
DEFAULT_INJECT_TYPE: str = "structuring"

# --- break_feed: degraded-data modes (Scenario C) ---------------------------
# mode -> (meta.data_quality, confidence_modifier). A broken feed must lower
# confidence and NEVER present a confident conclusion.
FEED_MODES: dict[str, tuple[str, float]] = {
    "stale": ("stale", 0.4),
    "late": ("degraded", 0.6),
}
DEFAULT_FEED_MODE: str = "stale"
