"""Forecast module — GET /api/forecast.

Serves one deterministic Forecast per pool plus the meta envelope. The soonest
`minutes_to_depletion` (the constraining pool for the hero) is trivially
derivable by the frontend from these four forecasts.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.common.meta import make_meta
from app.core.db import get_session
from app.modules.forecast.service import ForecastResult, compute_forecasts
from app.modules.forecast.schemas import (
    ConfidenceFactors,
    ForecastOut,
    ForecastResponse,
    HistoryPoint,
)

router = APIRouter(prefix="/api", tags=["forecast"])


def _iso_z(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_out(r: ForecastResult) -> ForecastOut:
    return ForecastOut(
        pool_id=r.pool_id,
        current_balance=r.current_balance,
        burn_rate_per_min=r.burn_rate_per_min,
        minutes_to_depletion=r.minutes_to_depletion,
        projected_depletion_ts=_iso_z(r.projected_depletion_ts) if r.projected_depletion_ts else None,
        confidence=r.confidence,
        recommended_action=r.recommended_action,
        evidence=r.evidence,
        status=r.status.value,
        trend=r.trend,
        projection_state=r.projection_state,
        confidence_factors=ConfidenceFactors(**r.confidence_factors),
        history=[HistoryPoint(ts=_iso_z(t), balance=b) for t, b in r.history],
    )


@router.get("/forecast", response_model=ForecastResponse)
def get_forecast(session: Session = Depends(get_session)) -> ForecastResponse:
    """Return a deterministic liquidity forecast for each pool."""
    results = compute_forecasts(session)
    return ForecastResponse(forecasts=[_to_out(r) for r in results], meta=make_meta())
