"""SQLModel tables for the case module: Case and its immutable CaseEvent trail.

Importing this module registers the tables on `SQLModel.metadata`, so it is
imported by `app.core.seed` and `app.main` before `create_all` runs. Table names
are set explicitly (`cases`, `case_events`) to avoid the SQL reserved word `case`.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class Case(SQLModel, table=True):
    """A coordination case auto-created from an alert. Advisory only.

    Mirrors the alert's `type` and `provider` (provider separation: a case never
    embeds another provider's data). `status`/`owner_role`/`escalation_level`
    move only through the guarded state machine in `service.py`; the append-only
    `CaseEvent` rows are the source of truth for the audit trail.
    """

    __tablename__ = "cases"

    id: str = Field(primary_key=True)  # e.g. "case_0003"
    alert_id: str = Field(foreign_key="alert.id", index=True)
    type: str                          # "liquidity" | "anomaly" (mirrors alert)
    provider: str | None = None        # null allowed (e.g. physical_cash)
    owner_role: str                    # field_officer|risk_reviewer|supervisor|area_manager
    status: str                        # raised|routed|acknowledged|escalated|resolved
    escalation_level: int = 0
    next_step: str
    recommended_action: str
    opened_ts: datetime
    updated_ts: datetime
    sla_minutes: int


class CaseEvent(SQLModel, table=True):
    """One immutable audit entry. Rows are only ever appended, never mutated.

    The autoincrement `id` is the stable ordering key, so entries that share a
    timestamp (e.g. `raised` and `routed` at auto-creation) keep their order.
    """

    __tablename__ = "case_events"

    id: int | None = Field(default=None, primary_key=True)  # append order
    case_id: str = Field(foreign_key="cases.id", index=True)
    stage: str                         # raised|routed|acknowledged|escalated|resolved
    actor: str                         # "system" | an owner role
    ts: datetime
    detail: str = ""
