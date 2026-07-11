"""Transactions module — recent transaction history with the meta envelope.

Returns transactions most-recent-first, optionally filtered by provider. Only
contract fields are serialized (via `TransactionOut`); the server-side anomaly
labels are never exposed.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.common.meta import make_meta
from app.core.db import get_session
from app.core.enums import Provider
from app.core.models import Transaction
from app.modules.transactions.schemas import (
    PoolEffectOut,
    TransactionOut,
    TransactionsResponse,
)

router = APIRouter(prefix="/api", tags=["transactions"])


def _iso_z(ts: datetime) -> str:
    """Serialize a stored UTC datetime as an ISO-8601 string with a `Z` suffix."""
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/transactions", response_model=TransactionsResponse)
def get_transactions(
    limit: int = Query(default=50, ge=1, le=1000),
    provider: Provider | None = Query(default=None),
    session: Session = Depends(get_session),
) -> TransactionsResponse:
    """Return recent transactions (newest first), optionally filtered by provider."""
    statement = select(Transaction)
    if provider is not None:
        statement = statement.where(Transaction.provider == provider.value)
    statement = statement.order_by(Transaction.ts.desc()).limit(limit)

    rows = session.exec(statement).all()
    items = [
        TransactionOut(
            id=t.id,
            ts=_iso_z(t.ts),
            provider=t.provider,
            txn_type=t.txn_type.value,
            amount=t.amount,
            status=t.status.value,
            account_id=t.account_id,
            area=t.area,
            event_flag=t.event_flag,
            pool_effects=[PoolEffectOut(**eff) for eff in t.pool_effects],
        )
        for t in rows
    ]
    return TransactionsResponse(transactions=items, meta=make_meta())
