"""Response + request schemas for the case module (contract Phase 4).

The audit trail is exposed as an ordered `history` array of `CaseEventOut`. No
field here transfers, blocks, freezes, or approves anything — the surface is
notify / assign / acknowledge / escalate / recommend / track only.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.common.meta import Meta


class CaseEventOut(BaseModel):
    """One immutable audit-trail entry."""

    stage: str
    actor: str
    ts: str
    detail: str


class CaseOut(BaseModel):
    id: str
    alert_id: str
    type: str                       # "liquidity" | "anomaly"
    provider: str | None            # null allowed
    owner_role: str
    status: str
    escalation_level: int
    next_step: str
    recommended_action: str
    opened_ts: str
    updated_ts: str
    sla_minutes: int
    history: list[CaseEventOut]


class CasesResponse(BaseModel):
    """GET /api/cases -> { cases: [Case, ...], meta }."""

    cases: list[CaseOut]
    meta: Meta


class TransitionRequest(BaseModel):
    """Body for ack / escalate / resolve. `actor` attributes the audit entry."""

    actor: str
    note: str = ""
