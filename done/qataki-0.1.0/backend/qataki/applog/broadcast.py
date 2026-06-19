"""Reusable in-process log broadcaster.

A ``logging.Handler`` that fans out records to any number of async subscribers
via per-subscriber ``asyncio.Queue``s. It has no framework or application
dependencies, so it can be lifted into a shared package unchanged. Pair it with
an SSE or WebSocket endpoint to stream logs live; combine with a file reader for
backfill on connect.

Thread-safety: ``emit`` may run on a worker thread, so puts are scheduled onto
the bound event loop via ``call_soon_threadsafe``. Each subscriber queue is
bounded; on overflow the oldest entry is dropped so logging never blocks.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional


class LogBroadcaster(logging.Handler):
    def __init__(
        self,
        maxsize: int = 1000,
        record_to_payload: Optional[Callable[[logging.LogRecord], Any]] = None,
    ):
        super().__init__()
        self._subs: set[asyncio.Queue] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._maxsize = maxsize
        self._to_payload = record_to_payload

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the event loop that subscriber queues live on (idempotent)."""
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._maxsize)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subs)

    def emit(self, record: logging.LogRecord) -> None:
        if not self._subs:
            return
        try:
            payload = self._to_payload(record) if self._to_payload else self.format(record)
        except Exception:  # never let logging raise
            return
        loop = self._loop
        for q in list(self._subs):
            if loop is not None and loop.is_running():
                loop.call_soon_threadsafe(self._offer, q, payload)
            else:
                self._offer(q, payload)

    @staticmethod
    def _offer(q: asyncio.Queue, payload: Any) -> None:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            try:
                q.get_nowait()  # drop oldest, keep newest
                q.put_nowait(payload)
            except Exception:
                pass
