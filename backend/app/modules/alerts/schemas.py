"""Response schemas for the alerts module (contract Phase 3).

Server-side detail (`covered_txn_ids`, `active_event` memo) is intentionally
absent from `AlertOut` so it can never leak via the API.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.common.meta import Meta


class AlertOut(BaseModel):
    id: str
    type: str                       # "liquidity" | "anomaly"
    severity: str                   # "low" | "medium" | "high"
    label: str
    anomaly_type: str | None        # null for liquidity
    provider: str | None
    pool_id: str
    evidence: list[str]
    baseline: dict
    observed: dict
    confidence: float
    ts: str
    case_id: str | None             # null until Phase 4


class Context(BaseModel):
    active_event: str
    note: str


class AlertsResponse(BaseModel):
    """GET /api/alerts -> { alerts: [Alert, ...], context: Context | null, meta }."""

    alerts: list[AlertOut]
    context: Context | None
    meta: Meta
