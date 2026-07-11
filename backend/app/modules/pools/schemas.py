"""Response schemas for the pools module (contract: Pool + meta envelope)."""

from __future__ import annotations

from pydantic import BaseModel

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
