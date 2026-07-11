"""Validation metric: SHORTAGE DETECTION LEAD TIME (one of our 3 required metrics).

Lead time = (actual depletion time) − (time status first went critical).

Method (deterministic, held-out replay): take the seeded physical-cash pool and
continue its observed eid-rush drain at the realized recent rate until the drawer
would cross its safety floor (the "actual depletion" ground truth). Replay that
trajectory minute-by-minute through the SAME forecast engine, feeding it only the
data available up to each step, and record the first minute its status becomes
`critical`. The gap between that moment and actual depletion is the lead time —
how much warning the system gives before the shortage bites.
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session

from app.core.enums import PoolId, PoolStatus
from app.modules.forecast.config import DEFAULT_CONFIG, ForecastConfig, safety_floor_for
from app.modules.forecast.service import (
    Effect,
    _pool_effects_from_db,
    compute_forecasts,
    forecast_pool,
)


def measure_lead_time(
    session: Session,
    cfg: ForecastConfig = DEFAULT_CONFIG,
    max_horizon_minutes: int = 240,
) -> dict:
    """Measure shortage-detection lead time for physical cash on the seeded data.

    Returns a dict with the lead time in minutes plus the intermediate values so
    the result is auditable, not a bare number.
    """
    pool_id = PoolId.physical_cash.value
    floor = safety_floor_for(pool_id)

    # Realized recent burn rate + current balance from the live forecast.
    physical = next(f for f in compute_forecasts(session, cfg=cfg) if f.pool_id == pool_id)
    rate = max(1, round(physical.ema_burn_rate))  # BDT/min drain
    current = physical.current_balance

    effects_by_pool, anchor = _pool_effects_from_db(session)
    base_effects: list[Effect] = list(effects_by_pool.get(pool_id, []))
    assert anchor is not None, "no seeded transactions"

    # Ground truth: continuing the drain, when does balance cross the floor?
    actual_depletion_min = (current - floor) / rate

    # Replay the continued drain through the engine, one minute at a time.
    first_critical_min: float | None = None
    horizon = min(max_horizon_minutes, int(actual_depletion_min) + 5)
    for k in range(1, horizon + 1):
        as_of = anchor + timedelta(minutes=k)
        # Synthetic continued cash-out: one -rate effect per elapsed minute.
        continued = [
            (anchor + timedelta(minutes=i + 0.5), -rate) for i in range(k)
        ]
        result = forecast_pool(
            pool_id=pool_id,
            effects=base_effects + continued,
            opening_balance=current - sum(d for _, d in base_effects),
            anchor=as_of,
            safety_floor=floor,
            cfg=cfg,
        )
        if result.status == PoolStatus.critical:
            first_critical_min = float(k)
            break

    lead_minutes = (
        round(actual_depletion_min - first_critical_min, 1)
        if first_critical_min is not None
        else None
    )
    return {
        "pool_id": pool_id,
        "burn_rate_per_min": rate,
        "current_balance": current,
        "safety_floor": floor,
        "actual_depletion_minutes": round(actual_depletion_min, 1),
        "first_critical_minutes": first_critical_min,
        "lead_time_minutes": lead_minutes,
    }
