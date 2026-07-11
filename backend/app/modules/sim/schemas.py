"""Request/response schemas for the sim controls (contract Phase 5).

Every control returns `{ ok, applied }`. Bodies mirror the contract examples and
carry safe defaults so a presenter can fire a control with an empty body.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.core.enums import Provider
from app.modules.sim import config as cfg


class StartRequest(BaseModel):
    speed: float = cfg.DEFAULT_SPEED       # ticks per second


class EidRushRequest(BaseModel):
    provider: str = "physical_cash"        # the pool under pressure
    intensity: str = "high"                # low | medium | high


class InjectAnomalyRequest(BaseModel):
    provider: Provider = Provider.rocket
    type: str = cfg.DEFAULT_INJECT_TYPE    # structuring | velocity_spike | off_hours_burst


class BreakFeedRequest(BaseModel):
    provider: Provider                     # only an e-money feed can degrade
    mode: str = cfg.DEFAULT_FEED_MODE      # stale | late


class RestoreFeedRequest(BaseModel):
    provider: Provider


class ControlResponse(BaseModel):
    ok: bool
    applied: str
