"""Process-wide SimulationClock accessor.

A single clock instance drives the stream and all controls. Tests inject a clock
bound to their own seeded engine via `set_clock`.
"""

from __future__ import annotations

from app.modules.sim.clock import SimulationClock

_clock: SimulationClock | None = None


def get_clock() -> SimulationClock:
    """Return the process clock, lazily bound to the default app engine."""
    global _clock
    if _clock is None:
        from app.core.db import engine
        _clock = SimulationClock(engine)
    return _clock


def set_clock(clock: SimulationClock | None) -> None:
    """Override (or clear) the process clock — used by tests."""
    global _clock
    _clock = clock
