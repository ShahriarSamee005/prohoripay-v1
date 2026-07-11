"""Configuration for the synthetic-data generator.

Everything the generator needs is here and config-driven, so more agents,
different balances, or different anomaly volumes can be added later without
touching generation logic. Only ONE agent is seeded now.

Reproducibility: a fixed seed + a fixed reference "now" make every run identical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class AgentSpec:
    """A super agent to seed, with its provider list and provider opening balances.

    `physical_cash` opening is derived by the generator so that the CURRENT
    physical cash lands exactly on `physical_target_current` (the hidden-shortage
    figure), regardless of the generated transaction mix.
    """

    id: str
    name: str
    area: str
    providers: tuple[str, ...]
    # Fixed opening balances for provider e-money pools (integer BDT).
    provider_openings: dict[str, int]
    # Desired CURRENT physical cash after all transactions — the constraining pool.
    physical_target_current: int = 80_000


# Fixed reference clock. Matches the contract's example date (2026-07-11) and
# keeps every seed deterministic (no wall-clock reads in generation).
REFERENCE_NOW: datetime = datetime(2026, 7, 11, 12, 0, 0)

# Reproducibility seed for numpy + Faker.
SEED: int = 1

CURRENCY: str = "BDT"

# The single primary agent for this prototype. `provider_openings` are chosen so
# the combined total looks healthy while physical cash is the sole constraint.
AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec(
        id="AGENT_07",
        name="Karim Store",
        area="Sylhet-Zindabazar",
        providers=("bkash", "nagad", "rocket"),
        provider_openings={"bkash": 120_000, "nagad": 45_000, "rocket": 100_000},
        physical_target_current=80_000,
    ),
)


@dataclass(frozen=True)
class AnomalySpec:
    """One labeled anomaly cluster injected into the history for Phase 3 validation."""

    anomaly_type: str
    provider: str
    count: int
    accounts: tuple[str, ...]
    amount_min: int
    amount_max: int
    window_start_sec: int  # seconds from midnight of the reference day
    window_end_sec: int
    event_flag: str | None


# Injected, labeled anomalies. Counts here define the exact ground truth the
# anomaly test asserts against (and Phase 3 measures precision/recall on).
#   (a) structuring     — repeated ~4,950 BDT from a 3-account cluster, 45 min
#   (b) velocity spike  — a burst of transactions in ~6 minutes
#   (c) off-hours burst — a cluster at ~03:00, well outside business hours
ANOMALIES: tuple[AnomalySpec, ...] = (
    AnomalySpec(
        anomaly_type="structuring",
        provider="bkash",
        count=12,
        accounts=("ACC_9001", "ACC_9002", "ACC_9003"),
        amount_min=4_910,
        amount_max=4_990,
        window_start_sec=11 * 3600,               # 11:00
        window_end_sec=11 * 3600 + 45 * 60,       # 11:45  (45 min)
        event_flag="eid_rush",
    ),
    AnomalySpec(
        anomaly_type="velocity_spike",
        provider="rocket",
        count=18,
        accounts=("ACC_9101", "ACC_9102"),
        amount_min=1_000,
        amount_max=3_000,
        window_start_sec=11 * 3600 + 30 * 60,     # 11:30
        window_end_sec=11 * 3600 + 36 * 60,       # 11:36  (6 min burst)
        event_flag="eid_rush",
    ),
    AnomalySpec(
        anomaly_type="off_hours_burst",
        provider="nagad",
        count=9,
        accounts=("ACC_9201", "ACC_9202"),
        amount_min=2_000,
        amount_max=4_000,
        window_start_sec=3 * 3600 + 5 * 60,       # 03:05  (off-hours)
        window_end_sec=3 * 3600 + 35 * 60,        # 03:35
        event_flag=None,
    ),
)

# Total number of labeled anomalies — the anomaly test asserts the DB holds
# exactly this many and that NONE of them leak through any API response.
EXPECTED_ANOMALY_COUNT: int = sum(a.count for a in ANOMALIES)


@dataclass(frozen=True)
class NormalTrafficSpec:
    """Volume/amount parameters for the non-anomalous background traffic."""

    # Calm baseline hour (09:00–10:00): balanced cash_in / cash_out.
    baseline_count: int = 26
    baseline_start_sec: int = 9 * 3600
    baseline_end_sec: int = 10 * 3600
    baseline_cashout_amount: tuple[int, int] = (500, 5_000)
    baseline_cashin_amount: tuple[int, int] = (1_000, 12_000)
    baseline_cashout_share: float = 0.5

    # Eid rush (10:00–12:00): heavy cash_out pressure on physical cash.
    eid_count: int = 70
    eid_start_sec: int = 10 * 3600
    eid_end_sec: int = 12 * 3600
    eid_cashout_amount: tuple[int, int] = (1_500, 9_000)
    eid_cashin_amount: tuple[int, int] = (1_000, 6_000)
    eid_cashout_share: float = 0.82

    # How cash_out volume is spread across providers (must cover all providers).
    provider_weights: dict[str, float] = field(
        default_factory=lambda: {"bkash": 0.45, "rocket": 0.35, "nagad": 0.20}
    )

    # Customer account-id pool for non-anomalous traffic.
    account_id_min: int = 1_000
    account_id_max: int = 1_400


NORMAL_TRAFFIC = NormalTrafficSpec()


# Pool-status thresholds (simple, ratio-of-opening headroom). Phase 2's forecast
# refines status; for now this cleanly makes the drained physical pool critical
# while the grown provider pools stay healthy.
STATUS_CRITICAL_RATIO: float = 0.50
STATUS_WATCH_RATIO: float = 0.80
