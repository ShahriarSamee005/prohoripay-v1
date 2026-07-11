"""Integrity test — proves the direction rule holds across the whole dataset.

For every pool: stored current_balance == opening_balance + sum(its signed
effects) across all transactions. If the direction-aware effects were ever
wrong, this equality would break.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.enums import PoolId
from app.core.models import Pool, Transaction


def test_current_balance_equals_opening_plus_signed_effects(db_session: Session):
    pools = db_session.exec(select(Pool)).all()
    transactions = db_session.exec(select(Transaction)).all()
    assert pools, "expected pools to be seeded"
    assert transactions, "expected transactions to be seeded"

    # Sum signed effects per pool straight from the transactions' pool_effects.
    net: dict[str, int] = {}
    for txn in transactions:
        for eff in txn.pool_effects:
            net[eff["pool_id"]] = net.get(eff["pool_id"], 0) + eff["delta"]

    for pool in pools:
        expected = pool.opening_balance + net.get(pool.pool_id, 0)
        assert pool.current_balance == expected, (
            f"{pool.pool_id}: stored current {pool.current_balance} != "
            f"opening {pool.opening_balance} + net effects {net.get(pool.pool_id, 0)}"
        )


def test_physical_cash_is_the_constraining_pool(db_session: Session):
    """The hidden-shortage scenario: physical cash is critical while total is healthy.

    "Constraining" is about headroom (it drained), not raw size — physical cash
    need not be the smallest number, which is exactly what makes the shortage
    *hidden* behind a healthy-looking total.
    """
    pools = {p.pool_id: p for p in db_session.exec(select(Pool)).all()}
    physical = pools[PoolId.physical_cash.value]
    providers = [p for pid, p in pools.items() if pid != PoolId.physical_cash.value]

    # Physical cash is the unique constrained (critical) pool...
    assert physical.status.value == "critical"
    assert physical.current_balance < physical.opening_balance  # it drained
    # ...while every provider pool is healthy (they grew under cash-out pressure).
    for p in providers:
        assert p.status.value == "healthy"

    # And the combined total across separate, non-interchangeable pools looks healthy.
    total = sum(p.current_balance for p in pools.values())
    assert total > physical.current_balance * 3
