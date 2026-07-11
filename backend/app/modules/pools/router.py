"""Pools module — serves the four balance pools with the meta envelope.

Ordering puts the shared physical cash pool first, then providers, matching the
hero framing (shared constraint first, provider breakdown beneath).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.common.meta import make_meta
from app.core.db import get_session
from app.core.enums import PoolId
from app.core.models import Pool
from app.modules.pools.schemas import PoolOut, PoolsResponse

router = APIRouter(prefix="/api", tags=["pools"])

# Stable display order: physical cash first, then providers.
_POOL_ORDER = {
    PoolId.physical_cash.value: 0,
    PoolId.bkash.value: 1,
    PoolId.nagad.value: 2,
    PoolId.rocket.value: 3,
}


@router.get("/pools", response_model=PoolsResponse)
def get_pools(session: Session = Depends(get_session)) -> PoolsResponse:
    """Return all balance pools plus the degraded-data meta envelope."""
    pools = session.exec(select(Pool)).all()
    pools = sorted(pools, key=lambda p: _POOL_ORDER.get(p.pool_id, 99))

    items = [
        PoolOut(
            pool_id=p.pool_id,
            kind=p.kind.value,
            provider=p.provider,
            label=p.label,
            balance=p.current_balance,
            currency=p.currency,
            status=p.status.value,
        )
        for p in pools
    ]
    return PoolsResponse(pools=items, meta=make_meta())
