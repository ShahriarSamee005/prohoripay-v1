"""Pools module — serves the four balance pools with the meta envelope.

Ordering puts the shared physical cash pool first, then providers, matching the
hero framing (shared constraint first, provider breakdown beneath).

Pool `status` is NOT read from the stored column — it comes from the forecast
engine (`pool_status_map`), so /api/pools and /api/forecast can never disagree.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.common.meta import make_meta
from app.core.db import get_session
from app.core.enums import PoolId, PoolStatus
from app.core.models import Pool
from app.modules.forecast.service import pool_status_map
from app.modules.pools.schemas import PatchCashBody, PatchCashResponse, PoolOut, PoolsResponse

router = APIRouter(prefix="/api", tags=["pools"])

# Stable display order: physical cash first, then providers.
_POOL_ORDER = {
    PoolId.physical_cash.value: 0,
    PoolId.bkash.value: 1,
    PoolId.nagad.value: 2,
    PoolId.rocket.value: 3,
}


@router.patch("/pools/physical_cash", response_model=PatchCashResponse)
def patch_physical_cash(
    body: PatchCashBody,
    session: Session = Depends(get_session),
) -> PatchCashResponse:
    """Human-recorded cash count.

    Updates the physical cash pool balance to exactly the value the human
    recorded. Advisory only — no transfer, no automatic action.
    """
    pool = session.get(Pool, PoolId.physical_cash.value)
    if pool is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Physical cash pool not found")
    pool.current_balance = body.balance
    session.add(pool)
    session.commit()
    session.refresh(pool)
    return PatchCashResponse(
        ok=True,
        pool_id=pool.pool_id,
        balance=pool.current_balance,
        note=body.note,
    )


@router.get("/pools", response_model=PoolsResponse)
def get_pools(session: Session = Depends(get_session)) -> PoolsResponse:
    """Return all balance pools (status is forecast-driven) plus the meta envelope."""
    pools = session.exec(select(Pool)).all()
    pools = sorted(pools, key=lambda p: _POOL_ORDER.get(p.pool_id, 99))

    # Single source of truth for status: the forecast engine.
    status_by_pool = pool_status_map(session)

    items = [
        PoolOut(
            pool_id=p.pool_id,
            kind=p.kind.value,
            provider=p.provider,
            label=p.label,
            balance=p.current_balance,
            currency=p.currency,
            status=status_by_pool.get(p.pool_id, PoolStatus.healthy).value,
        )
        for p in pools
    ]
    return PoolsResponse(pools=items, meta=make_meta())
