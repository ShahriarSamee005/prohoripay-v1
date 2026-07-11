"""Response schemas for the transactions module (contract: Transaction + meta).

Note: the server-side-only ground-truth fields (`is_injected_anomaly`,
`anomaly_type`) are deliberately absent here, so they can never leak via the API.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.common.meta import Meta


class PoolEffectOut(BaseModel):
    """A signed, pool-specific effect: how one pool's balance moved."""

    pool_id: str
    delta: int


class TransactionOut(BaseModel):
    """A single direction-aware transaction (contract shape)."""

    id: str
    ts: str
    provider: str
    txn_type: str
    amount: int
    status: str
    account_id: str
    area: str
    event_flag: str | None
    pool_effects: list[PoolEffectOut]


class TransactionsResponse(BaseModel):
    """GET /api/transactions -> { transactions: [Transaction, ...], meta: Meta }."""

    transactions: list[TransactionOut]
    meta: Meta
