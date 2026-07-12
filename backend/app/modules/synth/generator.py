"""Deterministic synthetic-data generator (Faker + numpy, fixed seed).

Builds one super agent, its four balance pools, and a ~3-hour transaction
history dominated by Eid-rush cash-out pressure, plus three clusters of labeled
anomalies. All balance movement flows through `build_pool_effects`, so the core
direction rule holds everywhere.

Design note — how the hidden-shortage figure is guaranteed:
    Physical cash CURRENT is pinned to `physical_target_current` by deriving the
    physical opening balance as `target - net_physical_effect`. Providers use
    fixed openings and grow under cash-out pressure. This keeps the invariant
    `current == opening + sum(effects)` exact for every pool while making
    physical cash the sole constraining pool.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
from faker import Faker
from sqlmodel import Session

from app.core.effects import build_pool_effects
from app.core.enums import PoolId, PoolKind, PoolStatus, Provider, TxnStatus, TxnType
from app.core.models import Agent, Pool, Transaction
from app.modules.synth import config as cfg

# Midnight of the reference day; all timestamps are offsets from here.
_DAY_START = datetime(cfg.REFERENCE_NOW.year, cfg.REFERENCE_NOW.month, cfg.REFERENCE_NOW.day)

_PROVIDER_LABELS = {"bkash": "bKash", "nagad": "Nagad", "rocket": "Rocket"}


@dataclass
class _Txn:
    """A generated transaction before it is assigned a chronological id."""

    ts: datetime
    provider: str
    txn_type: TxnType
    amount: int
    account_id: str
    event_flag: str | None
    is_injected_anomaly: bool
    anomaly_type: str | None


def _ts_from_sec(seconds: float) -> datetime:
    return _DAY_START + timedelta(seconds=int(seconds))


def _pool_status(current: int, opening: int) -> PoolStatus:
    """Simple ratio-of-opening headroom status (Phase 2 forecast refines this)."""
    ratio = current / opening if opening > 0 else 0.0
    if ratio < cfg.STATUS_CRITICAL_RATIO:
        return PoolStatus.critical
    if ratio < cfg.STATUS_WATCH_RATIO:
        return PoolStatus.watch
    return PoolStatus.healthy


def _weighted_providers(spec: cfg.AgentSpec, rng: np.random.RandomState, n: int) -> list[str]:
    """Pick `n` providers according to the configured cash-out weights."""
    providers = list(spec.providers)
    weights = np.array([cfg.NORMAL_TRAFFIC.provider_weights[p] for p in providers], dtype=float)
    weights = weights / weights.sum()
    return list(rng.choice(providers, size=n, p=weights))


def _sorted_times(rng: np.random.RandomState, start_sec: int, end_sec: int, n: int) -> list[float]:
    return sorted(rng.uniform(start_sec, end_sec, size=n).tolist())


def _generate_normal(spec: cfg.AgentSpec, rng: np.random.RandomState) -> list[_Txn]:
    """Baseline (calm) + Eid-rush (cash-out heavy) non-anomalous traffic."""
    nt = cfg.NORMAL_TRAFFIC
    out: list[_Txn] = []

    def account() -> str:
        return f"ACC_{rng.randint(nt.account_id_min, nt.account_id_max)}"

    for (count, start, end, cashout_share, cashout_amt, cashin_amt, flag) in (
        (
            nt.baseline_count, nt.baseline_start_sec, nt.baseline_end_sec,
            nt.baseline_cashout_share, nt.baseline_cashout_amount, nt.baseline_cashin_amount,
            None,
        ),
        (
            nt.eid_count, nt.eid_start_sec, nt.eid_end_sec,
            nt.eid_cashout_share, nt.eid_cashout_amount, nt.eid_cashin_amount,
            "eid_rush",
        ),
    ):
        times = _sorted_times(rng, start, end, count)
        providers = _weighted_providers(spec, rng, count)
        for t_sec, provider in zip(times, providers):
            is_cashout = rng.random_sample() < cashout_share
            if is_cashout:
                txn_type = TxnType.cash_out
                amount = int(rng.randint(cashout_amt[0], cashout_amt[1]))
            else:
                txn_type = TxnType.cash_in
                amount = int(rng.randint(cashin_amt[0], cashin_amt[1]))
            out.append(
                _Txn(
                    ts=_ts_from_sec(t_sec),
                    provider=provider,
                    txn_type=txn_type,
                    amount=amount,
                    account_id=account(),
                    event_flag=flag,
                    is_injected_anomaly=False,
                    anomaly_type=None,
                )
            )
    return out


def _generate_anomalies(rng: np.random.RandomState) -> list[_Txn]:
    """The three labeled anomaly clusters (all cash_out, all tagged)."""
    out: list[_Txn] = []
    for spec in cfg.ANOMALIES:
        times = _sorted_times(rng, spec.window_start_sec, spec.window_end_sec, spec.count)
        for t_sec in times:
            amount = int(rng.randint(spec.amount_min, spec.amount_max + 1))
            account_id = spec.accounts[rng.randint(0, len(spec.accounts))]
            out.append(
                _Txn(
                    ts=_ts_from_sec(t_sec),
                    provider=spec.provider,
                    txn_type=TxnType.cash_out,
                    amount=amount,
                    account_id=account_id,
                    event_flag=spec.event_flag,
                    is_injected_anomaly=True,
                    anomaly_type=spec.anomaly_type,
                )
            )
    return out


def _build_pools(spec: cfg.AgentSpec, net_by_pool: dict[str, int]) -> list[Pool]:
    """Create the four pools, deriving physical opening from the target current."""
    pools: list[Pool] = []

    # Physical cash: pin CURRENT to the target; derive opening from net effects.
    phys_net = net_by_pool.get(PoolId.physical_cash.value, 0)
    phys_current = spec.physical_target_current
    phys_opening = phys_current - phys_net
    pools.append(
        Pool(
            pool_id=PoolId.physical_cash.value,
            agent_id=spec.id,
            kind=PoolKind.physical_cash,
            provider=None,
            label="Physical Cash",
            opening_balance=phys_opening,
            current_balance=phys_current,
            currency=cfg.CURRENCY,
            status=_pool_status(phys_current, phys_opening),
        )
    )

    # Provider e-money pools: fixed opening, current = opening + net effects.
    for provider in spec.providers:
        opening = spec.provider_openings[provider]
        current = opening + net_by_pool.get(provider, 0)
        pools.append(
            Pool(
                pool_id=provider,
                agent_id=spec.id,
                kind=PoolKind.provider_emoney,
                provider=provider,
                label=_PROVIDER_LABELS.get(provider, provider),
                opening_balance=opening,
                current_balance=current,
                currency=cfg.CURRENCY,
                status=_pool_status(current, opening),
            )
        )
    return pools


def populate_salary_day(session: Session) -> dict:
    """Salary-day stress scenario: heavy cash-in drains the bKash provider float.

    In the default Eid scenario, cash_out pressure drains *physical* cash.  Here,
    cash_in pressure during the salary window drains the *bKash* provider float
    while physical cash grows — the inverse stress pattern.  The existing forecast
    engine (unchanged) surfaces bKash as the constraining pool when run against
    this dataset.

    Uses SALARY_DAY_SEED so the output is fully deterministic.
    """
    _sal_day_start = datetime(
        cfg.SALARY_DAY_REFERENCE_NOW.year,
        cfg.SALARY_DAY_REFERENCE_NOW.month,
        cfg.SALARY_DAY_REFERENCE_NOW.day,
    )

    def _ts_sal(seconds: float) -> datetime:
        return _sal_day_start + timedelta(seconds=int(seconds))

    rng = np.random.RandomState(cfg.SALARY_DAY_SEED)
    Faker.seed(cfg.SALARY_DAY_SEED)

    spec = cfg.SALARY_DAY_AGENT
    sd = cfg.SALARY_DAY_TRAFFIC

    def account() -> str:
        return f"ACC_{rng.randint(sd.account_id_min, sd.account_id_max)}"

    raw: list[_Txn] = []
    times = _sorted_times(rng, sd.start_sec, sd.end_sec, sd.count)
    for t_sec in times:
        is_cashin = rng.random_sample() < sd.cashin_share
        if rng.random_sample() < sd.bkash_share:
            provider = "bkash"
        else:
            others = [p for p in spec.providers if p != "bkash"]
            provider = str(rng.choice(others))

        if is_cashin:
            txn_type = TxnType.cash_in
            amount = int(rng.randint(sd.cashin_amount[0], sd.cashin_amount[1]))
        else:
            txn_type = TxnType.cash_out
            amount = int(rng.randint(sd.cashout_amount[0], sd.cashout_amount[1]))

        raw.append(
            _Txn(
                ts=_ts_sal(t_sec),
                provider=provider,
                txn_type=txn_type,
                amount=amount,
                account_id=account(),
                event_flag="salary_day",
                is_injected_anomaly=False,
                anomaly_type=None,
            )
        )

    raw.sort(key=lambda t: t.ts)

    net_by_pool: dict[str, int] = {}
    txn_rows: list[Transaction] = []
    for i, t in enumerate(raw, start=1):
        effects = build_pool_effects(TxnType(t.txn_type), Provider(t.provider), t.amount)
        for eff in effects:
            net_by_pool[eff["pool_id"]] = net_by_pool.get(eff["pool_id"], 0) + eff["delta"]
        txn_rows.append(
            Transaction(
                id=f"sal_{i:05d}",
                agent_id=spec.id,
                ts=t.ts,
                provider=t.provider,
                txn_type=t.txn_type,
                amount=t.amount,
                status=TxnStatus.completed,
                account_id=t.account_id,
                area=spec.area,
                event_flag=t.event_flag,
                pool_effects=effects,
                is_injected_anomaly=False,
                anomaly_type=None,
            )
        )

    agent = Agent(id=spec.id, name=spec.name, area=spec.area, providers=list(spec.providers))
    pools = _build_pools(spec, net_by_pool)

    session.add(agent)
    for pool in pools:
        session.add(pool)
    for txn in txn_rows:
        session.add(txn)
    session.commit()

    bkash_pool = next(p for p in pools if p.pool_id == "bkash")
    physical_pool = next(p for p in pools if p.pool_id == "physical_cash")
    return {
        "scenario": "salary_day",
        "transactions": len(txn_rows),
        "bkash_current": bkash_pool.current_balance,
        "bkash_opening": bkash_pool.opening_balance,
        "bkash_status": bkash_pool.status.value,
        "physical_current": physical_pool.current_balance,
        "physical_status": physical_pool.status.value,
        "pools": {p.pool_id: {"opening": p.opening_balance, "current": p.current_balance,
                               "status": p.status.value} for p in pools},
    }


def populate(session: Session) -> dict:
    """Generate and persist the full dataset into `session`. Returns a summary.

    Idempotency is the caller's job — `seed_database` resets the schema first.
    """
    rng = np.random.RandomState(cfg.SEED)
    Faker.seed(cfg.SEED)
    _ = Faker()  # seeded; reserved for richer synthetic detail in later phases

    spec = cfg.AGENTS[0]

    # 1. Generate all transactions, then order chronologically for stable ids.
    raw = _generate_normal(spec, rng) + _generate_anomalies(rng)
    raw.sort(key=lambda t: t.ts)

    # 2. Materialize Transaction rows with signed pool_effects + net tally.
    net_by_pool: dict[str, int] = {}
    txn_rows: list[Transaction] = []
    for i, t in enumerate(raw, start=1):
        effects = build_pool_effects(TxnType(t.txn_type), Provider(t.provider), t.amount)
        for eff in effects:
            net_by_pool[eff["pool_id"]] = net_by_pool.get(eff["pool_id"], 0) + eff["delta"]
        txn_rows.append(
            Transaction(
                id=f"txn_{i:05d}",
                agent_id=spec.id,
                ts=t.ts,
                provider=t.provider,
                txn_type=t.txn_type,
                amount=t.amount,
                status=TxnStatus.completed,
                account_id=t.account_id,
                area=spec.area,
                event_flag=t.event_flag,
                pool_effects=effects,
                is_injected_anomaly=t.is_injected_anomaly,
                anomaly_type=t.anomaly_type,
            )
        )

    # 3. Build pools from the net effects and persist everything.
    agent = Agent(id=spec.id, name=spec.name, area=spec.area, providers=list(spec.providers))
    pools = _build_pools(spec, net_by_pool)

    session.add(agent)
    for pool in pools:
        session.add(pool)
    for txn in txn_rows:
        session.add(txn)
    session.commit()

    anomaly_count = sum(1 for t in txn_rows if t.is_injected_anomaly)
    return {
        "agent_id": spec.id,
        "transactions": len(txn_rows),
        "anomalies": anomaly_count,
        "pools": {p.pool_id: {"opening": p.opening_balance,
                              "current": p.current_balance,
                              "status": p.status.value} for p in pools},
    }
