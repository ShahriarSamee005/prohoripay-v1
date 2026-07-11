"""Per-tick synthetic-traffic generation for the simulation clock.

Produces the next batch of direction-aware transactions for one tick — calm
baseline traffic plus any active injections (eid_rush pressure, a labeled anomaly
cluster). Every transaction is signed and pool-specific via `build_pool_effects`,
so the core direction rule holds exactly as in the seeded history.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.core.enums import TxnType
from app.modules.sim import config as cfg


@dataclass
class TickPlan:
    """What to generate on a single tick."""

    baseline_count: int = cfg.BASELINE_COUNT
    eid_cashout_count: int = 0                 # extra cash-out (eid_rush surge)
    inject_type: str | None = None             # anomaly preset key, if injecting
    inject_provider: str | None = None         # provider the cluster hits


@dataclass
class RawTxn:
    """A generated transaction before it is assigned a chronological id."""

    provider: str
    txn_type: TxnType
    amount: int
    account_id: str
    event_flag: str | None = None
    is_injected_anomaly: bool = False
    anomaly_type: str | None = None
    extra: dict = field(default_factory=dict)


_PROVIDERS = tuple(cfg.PROVIDER_WEIGHTS.keys())
_WEIGHTS = np.array([cfg.PROVIDER_WEIGHTS[p] for p in _PROVIDERS], dtype=float)
_WEIGHTS = _WEIGHTS / _WEIGHTS.sum()


def _pick_provider(rng: np.random.RandomState) -> str:
    return str(rng.choice(_PROVIDERS, p=_WEIGHTS))


def _account(rng: np.random.RandomState) -> str:
    return f"ACC_{rng.randint(cfg.BASELINE_ACCOUNT_MIN, cfg.BASELINE_ACCOUNT_MAX)}"


def generate_tick(rng: np.random.RandomState, plan: TickPlan) -> list[RawTxn]:
    """Build the raw transactions for one tick (deterministic given `rng`)."""
    out: list[RawTxn] = []

    # 1. Calm baseline: balanced cash_in / cash_out, small amounts, low volume.
    for _ in range(plan.baseline_count):
        provider = _pick_provider(rng)
        if rng.random_sample() < cfg.BASELINE_CASHOUT_SHARE:
            amount = int(rng.randint(*cfg.BASELINE_CASHOUT_AMOUNT))
            out.append(RawTxn(provider, TxnType.cash_out, amount, _account(rng)))
        else:
            amount = int(rng.randint(*cfg.BASELINE_CASHIN_AMOUNT))
            out.append(RawTxn(provider, TxnType.cash_in, amount, _account(rng)))

    # 2. Eid-rush surge: sustained cash_out (drains physical cash → Scenario A).
    for _ in range(plan.eid_cashout_count):
        provider = _pick_provider(rng)
        amount = int(rng.randint(*cfg.EID_CASHOUT_AMOUNT))
        out.append(RawTxn(provider, TxnType.cash_out, amount, _account(rng),
                          event_flag="eid_rush"))

    # 3. Injected anomaly cluster (labeled; detection catches it next tick).
    if plan.inject_type:
        preset = cfg.INJECT_PRESETS[plan.inject_type]
        provider = plan.inject_provider or _pick_provider(rng)
        accounts = preset["accounts"]
        for _ in range(preset["count"]):
            amount = int(rng.randint(preset["amount"][0], preset["amount"][1] + 1))
            account = accounts[rng.randint(0, len(accounts))]
            out.append(RawTxn(
                provider=provider,
                txn_type=TxnType.cash_out,
                amount=amount,
                account_id=account,
                is_injected_anomaly=True,
                anomaly_type=plan.inject_type,
            ))
    return out
