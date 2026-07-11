"""SQLModel tables — the persisted domain (Agent, Pool, Transaction).

Shapes follow `shared/contract.md` exactly. Importing this module registers the
tables on `SQLModel.metadata`, so it must be imported before `init_db()` runs.

The Transaction table additionally stores server-side-only ground-truth labels
(`is_injected_anomaly`, `anomaly_type`) used ONLY for Phase 3 validation. These
are NEVER included in any API response schema.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

from app.core.enums import PoolKind, PoolStatus, TxnStatus, TxnType


class Agent(SQLModel, table=True):
    """A multi-provider super agent. One physical drawer, separate e-money pools."""

    id: str = Field(primary_key=True)  # e.g. "AGENT_07"
    name: str
    area: str
    # List of provider string values, e.g. ["bkash", "nagad", "rocket"].
    providers: list[str] = Field(sa_column=Column(JSON))


class Pool(SQLModel, table=True):
    """A balance pool. `physical_cash` is shared; each provider has its own.

    Both `opening_balance` and `current_balance` are stored. The invariant
    `current_balance == opening_balance + sum(signed effects)` holds by
    construction (see the generator) and is asserted by the integrity test.
    """

    pool_id: str = Field(primary_key=True)  # PoolId value
    agent_id: str = Field(foreign_key="agent.id", index=True)
    kind: PoolKind
    provider: str | None = None  # None for the shared physical cash pool
    label: str
    opening_balance: int
    current_balance: int
    currency: str = "BDT"
    status: PoolStatus


class Transaction(SQLModel, table=True):
    """A single, direction-aware transaction.

    `pool_effects` is the source of truth for how balances move and is always
    built by `app.core.effects.build_pool_effects`.
    """

    id: str = Field(primary_key=True)  # e.g. "txn_00001"
    agent_id: str = Field(foreign_key="agent.id", index=True)
    ts: datetime = Field(index=True)
    provider: str
    txn_type: TxnType
    amount: int  # positive integer BDT
    status: TxnStatus
    account_id: str
    area: str
    event_flag: str | None = None  # "eid_rush" | "salary_day" | None
    # List of {"pool_id": str, "delta": int} — signed, pool-specific effects.
    pool_effects: list[dict] = Field(sa_column=Column(JSON))

    # --- Server-side-only ground truth. NEVER returned by any API. ---
    is_injected_anomaly: bool = Field(default=False, index=True)
    anomaly_type: str | None = None


class Alert(SQLModel, table=True):
    """A persisted alert (contract Phase 3). Anomaly or liquidity.

    `covered_txn_ids` is a server-side detail (which transactions the detector's
    evidence covers) used for precision/recall validation and Phase-4 case
    linkage. It is NEVER included in the API response schema.
    """

    id: str = Field(primary_key=True)  # e.g. "alert_0007"
    type: str                          # "liquidity" | "anomaly"
    severity: str                      # "low" | "medium" | "high"
    label: str
    anomaly_type: str | None = None    # null for liquidity
    provider: str | None = None        # null allowed (e.g. physical_cash)
    pool_id: str
    evidence: list[str] = Field(sa_column=Column(JSON))
    baseline: dict = Field(default_factory=dict, sa_column=Column(JSON))
    observed: dict = Field(default_factory=dict, sa_column=Column(JSON))
    confidence: float
    ts: datetime = Field(index=True)
    case_id: str | None = None         # null until Phase 4 creates a case

    # --- Server-side only. NEVER returned by any API. ---
    covered_txn_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    active_event: str | None = None    # event that contextualized this alert, if any
