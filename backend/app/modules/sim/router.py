"""Sim module — GET /api/stream (SSE) + presenter-driven controls.

The stream registers a per-client queue and yields `event:/data:` frames with
periodic keep-alive comments, cleaning up on disconnect. Controls mutate the
clock and return `{ ok, applied }`; feed_status is flushed immediately so live
clients see a broken/restored feed without waiting for the next tick.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.modules.sim import config as cfg
from app.modules.sim.schemas import (
    BreakFeedRequest,
    ControlResponse,
    EidRushRequest,
    InjectAnomalyRequest,
    RestoreFeedRequest,
    StartRequest,
)
from app.modules.sim.service import get_clock

router = APIRouter(prefix="/api", tags=["sim"])


def _ok(applied: str) -> ControlResponse:
    return ControlResponse(ok=True, applied=applied)


@router.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    """Server-Sent Events stream of live sim changes (one queue per client)."""
    clock = get_clock()
    queue = clock.bus.subscribe()

    async def event_generator():
        try:
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=cfg.KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
        finally:
            clock.bus.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                 "X-Accel-Buffering": "no"},
    )


# ------------------------------------------------------------------- controls
@router.post("/sim/start", response_model=ControlResponse)
async def sim_start(body: StartRequest | None = None) -> ControlResponse:
    clock = get_clock()
    applied = clock.start((body or StartRequest()).speed)
    await clock.flush_and_publish()
    return _ok(applied)


@router.post("/sim/pause", response_model=ControlResponse)
async def sim_pause() -> ControlResponse:
    return _ok(get_clock().pause())


@router.post("/sim/reset", response_model=ControlResponse)
async def sim_reset() -> ControlResponse:
    return _ok(get_clock().reset())


@router.post("/sim/eid_rush", response_model=ControlResponse)
async def sim_eid_rush(body: EidRushRequest | None = None) -> ControlResponse:
    body = body or EidRushRequest()
    clock = get_clock()
    applied = clock.eid_rush(provider=body.provider, intensity=body.intensity)
    await clock.flush_and_publish()
    return _ok(applied)


@router.post("/sim/inject_anomaly", response_model=ControlResponse)
async def sim_inject_anomaly(body: InjectAnomalyRequest | None = None) -> ControlResponse:
    body = body or InjectAnomalyRequest()
    clock = get_clock()
    applied = clock.inject_anomaly(provider=body.provider.value, type=body.type)
    await clock.flush_and_publish()
    return _ok(applied)


@router.post("/sim/break_feed", response_model=ControlResponse)
async def sim_break_feed(body: BreakFeedRequest) -> ControlResponse:
    clock = get_clock()
    applied = clock.break_feed(provider=body.provider.value, mode=body.mode)
    await clock.flush_and_publish()  # emit feed_status now
    return _ok(applied)


@router.post("/sim/restore_feed", response_model=ControlResponse)
async def sim_restore_feed(body: RestoreFeedRequest) -> ControlResponse:
    clock = get_clock()
    applied = clock.restore_feed(provider=body.provider.value)
    await clock.flush_and_publish()
    return _ok(applied)
