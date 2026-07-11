"""In-memory pub/sub for the SSE stream — one asyncio.Queue per subscriber.

The clock publishes typed events; each connected SSE client owns a queue and
drains it. Publishing never blocks the clock: if a slow client's queue is full,
that event is dropped for that client only (it can re-fetch REST snapshots on
reconnect, per the contract).
"""

from __future__ import annotations

import asyncio

# Bound per-subscriber queue: a slow client cannot grow memory without limit.
_MAX_QUEUE = 1000


class Broadcaster:
    """Fan-out of events to all subscribed queues."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        """Register and return a fresh queue for one client."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=_MAX_QUEUE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Drop a client's queue (on disconnect)."""
        self._subscribers.discard(queue)

    async def publish(self, event: dict) -> None:
        """Fan an event out to every subscriber. Full queues drop the event."""
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # slow client: drop; it recovers via REST snapshot on reconnect

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
