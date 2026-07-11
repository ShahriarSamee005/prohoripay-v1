"""Direction test — every transaction's effects obey the core domain rule.

    cash_out -> physical_cash delta < 0 , provider delta > 0
    cash_in  -> physical_cash delta > 0 , provider delta < 0
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.effects import build_pool_effects
from app.core.enums import PoolId, Provider, TxnType
from app.core.models import Transaction


def _effects_by_pool(pool_effects: list[dict]) -> dict[str, int]:
    return {eff["pool_id"]: eff["delta"] for eff in pool_effects}


def test_every_transaction_is_direction_correct(db_session: Session):
    transactions = db_session.exec(select(Transaction)).all()
    assert transactions

    for txn in transactions:
        effects = _effects_by_pool(txn.pool_effects)
        physical = effects[PoolId.physical_cash.value]
        provider = effects[txn.provider]

        # Amount is always positive; direction lives only in the deltas.
        assert txn.amount > 0
        assert abs(physical) == txn.amount
        assert abs(provider) == txn.amount

        if txn.txn_type == TxnType.cash_out:
            assert physical < 0 and provider > 0
        else:  # cash_in
            assert physical > 0 and provider < 0


def test_effects_helper_is_symmetric():
    """The single helper encodes the rule; a cash_in reverses a cash_out."""
    out = _effects_by_pool(build_pool_effects(TxnType.cash_out, Provider.bkash, 9500))
    inp = _effects_by_pool(build_pool_effects(TxnType.cash_in, Provider.bkash, 9500))

    assert out[PoolId.physical_cash.value] == -9500
    assert out[PoolId.bkash.value] == 9500
    assert inp[PoolId.physical_cash.value] == 9500
    assert inp[PoolId.bkash.value] == -9500
