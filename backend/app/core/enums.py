"""Shared domain enums — the single source of truth for the contract's core enums.

Kept in `core/` because both the SQLModel tables and every module's response
schema reference them. All are `str`-backed so they serialize to their string
value in both SQLite and JSON.
"""

from __future__ import annotations

from enum import Enum


class PoolId(str, Enum):
    """Identifier for a balance pool. One shared cash pool + one per provider."""

    physical_cash = "physical_cash"
    bkash = "bkash"
    nagad = "nagad"
    rocket = "rocket"


class PoolKind(str, Enum):
    """A pool is either the single shared cash drawer or a provider e-money pool."""

    physical_cash = "physical_cash"
    provider_emoney = "provider_emoney"


class Provider(str, Enum):
    """E-money rails only. The physical cash pool has no provider."""

    bkash = "bkash"
    nagad = "nagad"
    rocket = "rocket"


class TxnType(str, Enum):
    """Direction of the transaction. See `app.core.effects` for the signed effects."""

    cash_in = "cash_in"
    cash_out = "cash_out"


class TxnStatus(str, Enum):
    completed = "completed"
    pending = "pending"
    failed = "failed"


class PoolStatus(str, Enum):
    """Operational status of a pool. Indicates state only — never a decision."""

    healthy = "healthy"
    watch = "watch"
    critical = "critical"
