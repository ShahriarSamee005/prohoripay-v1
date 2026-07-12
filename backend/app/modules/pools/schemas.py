"""Response schemas for the pools module (contract: Pool + meta envelope)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.common.meta import Meta


class PoolOut(BaseModel):
    """A single balance pool. `balance` is the stored current balance."""

    pool_id: str
    kind: str
    provider: str | None
    label: str
    balance: int
    currency: str
    status: str


class PoolsResponse(BaseModel):
    """GET /api/pools -> { pools: [Pool, ...], meta: Meta }."""

    pools: list[PoolOut]
    meta: Meta


class PatchCashBody(BaseModel):
    """PATCH /api/pools/physical_cash — human-recorded cash count."""

    balance: int = Field(ge=0, description="New physical cash balance (BDT, integer ≥ 0)")
    note: str | None = Field(
        default=None,
        max_length=200,
        description="Optional human note (e.g. 'counted at 14:30')",
    )


class PatchCashResponse(BaseModel):
    """Response from PATCH /api/pools/physical_cash."""

    ok: bool
    pool_id: str
    balance: int
    note: str | None
