"""The ONE direction-aware effects helper.

This is the single place the core domain rule is encoded, so it cannot drift:

    cash_out -> physical_cash -amount , provider +amount   (customer takes cash)
    cash_in  -> physical_cash +amount , provider -amount   (customer deposits cash)

Physical cash (shared) and provider e-money (separate) move in OPPOSITE
directions. Every transaction's `pool_effects` MUST come from here. Amounts are
always positive; the sign lives entirely in the `delta`.
"""

from __future__ import annotations

from app.core.enums import PoolId, Provider, TxnType


def build_pool_effects(txn_type: TxnType, provider: Provider, amount: int) -> list[dict]:
    """Return the signed, pool-specific effects for one transaction.

    Args:
        txn_type: `cash_out` or `cash_in`.
        provider: the e-money rail involved (bkash / nagad / rocket).
        amount: a strictly positive integer BDT amount.

    Returns:
        A two-element list of ``{"pool_id": ..., "delta": ...}`` dicts: one for
        the shared physical cash pool, one for the provider's e-money pool.
    """
    if amount <= 0:
        raise ValueError("amount must be a positive integer BDT value")

    provider_id = PoolId(provider.value)

    if txn_type == TxnType.cash_out:
        # Customer hands over e-money, walks away with physical cash.
        return [
            {"pool_id": PoolId.physical_cash.value, "delta": -amount},
            {"pool_id": provider_id.value, "delta": amount},
        ]

    if txn_type == TxnType.cash_in:
        # Customer deposits physical cash, receives e-money.
        return [
            {"pool_id": PoolId.physical_cash.value, "delta": amount},
            {"pool_id": provider_id.value, "delta": -amount},
        ]

    raise ValueError(f"unknown txn_type: {txn_type!r}")
