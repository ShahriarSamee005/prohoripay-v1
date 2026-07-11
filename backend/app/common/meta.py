"""Shared `meta` object for analytics-bearing responses (Degraded-data convention).

Every response that carries analytics includes a `meta` per `shared/contract.md`.
In Phase 1 all data is fresh and complete, so it is always
`{ data_quality: "ok", confidence_modifier: 1.0 }`. Later phases lower these when
a provider feed is late/missing/conflicting.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel


def _utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string with a trailing `Z`."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Meta(BaseModel):
    """The degraded-data envelope carried by analytics responses."""

    generated_at: str
    data_quality: Literal["ok", "degraded", "stale"] = "ok"
    confidence_modifier: float = 1.0


def make_meta(
    data_quality: Literal["ok", "degraded", "stale"] = "ok",
    confidence_modifier: float = 1.0,
) -> Meta:
    """Build a `Meta` stamped with the current UTC time."""
    return Meta(
        generated_at=_utc_now_iso(),
        data_quality=data_quality,
        confidence_modifier=confidence_modifier,
    )
