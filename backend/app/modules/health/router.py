"""Health module — liveness endpoint.

Self-contained: router + response schema live here. Reports service liveness
and the current UTC time, per the Phase 0 contract.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Contract: GET /health -> { status, time (ISO-8601 UTC) }."""

    status: str
    time: str


def _utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string with a trailing `Z`."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return service liveness and current UTC timestamp."""
    return HealthResponse(status="ok", time=_utc_now_iso())
