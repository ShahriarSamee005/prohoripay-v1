"""Response schemas for the forecast module.

Contract fields (final): pool_id, current_balance, burn_rate_per_min,
minutes_to_depletion, projected_depletion_ts, confidence, recommended_action,
evidence.

Additive fields (proposed in Phase 2, additive — no contract field changed):
  * status            — forecast-derived pool status (single source of truth).
  * trend             — accelerating | easing | steady | filling.
  * confidence_factors — the earned-confidence breakdown.
  * history           — bucketed balance series for the burn-down chart.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.common.meta import Meta


class ConfidenceFactors(BaseModel):
    # Named to match the frontend contract in lib/types.ts.
    volatility: float      # 0–1: share of confidence lost to high variance
    sample_size: float     # 0–1: normalised sample saturation (not raw count)
    data_freshness: float  # 0–1: feed freshness modifier


class HistoryPoint(BaseModel):
    ts: str
    balance: int


class ForecastOut(BaseModel):
    # --- contract fields ---
    pool_id: str
    current_balance: int
    burn_rate_per_min: int
    minutes_to_depletion: float | None
    projected_depletion_ts: str | None
    confidence: float
    recommended_action: str
    evidence: list[str]
    # --- additive fields (Phase 2) ---
    safety_floor: int
    status: str
    trend: str
    # at_floor | insufficient_data | intermittent | filling | projected
    projection_state: str
    confidence_factors: ConfidenceFactors
    history: list[HistoryPoint]


class ForecastResponse(BaseModel):
    """GET /api/forecast -> { forecasts: [Forecast, ...], meta: Meta }."""

    forecasts: list[ForecastOut]
    meta: Meta
