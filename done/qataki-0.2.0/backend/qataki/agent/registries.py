"""
Session-scoped ToolRegistry-Pool.

Ein Browser (eine ToolRegistry) pro Run, ueber mehrere Chat-Nachrichten hinweg
wiederverwendet — damit die geoeffnete Seite zwischen den Nachrichten erhalten
bleibt. Geschlossen wird erst bei: Run-Loeschen, NOTAUS, Idle-Timeout und
Server-Stopp. Der Wechsel auf einen anderen Run laesst bestehende Browser
unberuehrt (jeder Run haelt seinen eigenen).
"""
from __future__ import annotations

import asyncio
import logging
import time

from uc_agent_core.registry import ToolRegistry

log = logging.getLogger("qataki.browsers")

IDLE_SECONDS = 15 * 60          # nach so langer Inaktivitaet schliessen
_SWEEP_SECONDS = 60             # Takt des Idle-Sweepers


class _Entry:
    __slots__ = ("reg", "last_active")

    def __init__(self, reg: ToolRegistry) -> None:
        self.reg = reg
        self.last_active = time.monotonic()


_pool: dict[str, _Entry] = {}
_lock = asyncio.Lock()
_sweeper_task: asyncio.Task | None = None


async def get(session_id: str, *, headless: bool, artifacts_path: str) -> ToolRegistry:
    """Bestehende Registry der Session liefern oder neu erzeugen. Markiert aktiv."""
    async with _lock:
        e = _pool.get(session_id)
        if e is None:
            reg = ToolRegistry(headless=headless, artifacts_path=artifacts_path)
            e = _Entry(reg)
            _pool[session_id] = e
            log.info("Browser-Registry erzeugt (session=%s, headless=%s)", session_id, headless)
        e.last_active = time.monotonic()
        return e.reg


async def close(session_id: str) -> bool:
    """Registry einer Session schliessen und entfernen. True, wenn vorhanden."""
    async with _lock:
        e = _pool.pop(session_id, None)
    if e is None:
        return False
    try:
        await e.reg.aclose()
    except Exception:
        pass
    log.info("Browser-Registry geschlossen (session=%s)", session_id)
    return True


async def close_all() -> int:
    """Alle Registries schliessen (NOTAUS / Server-Stopp). Anzahl zurueck."""
    async with _lock:
        items = list(_pool.items())
        _pool.clear()
    for _sid, e in items:
        try:
            await e.reg.aclose()
        except Exception:
            pass
    if items:
        log.info("Alle Browser-Registries geschlossen (%d)", len(items))
    return len(items)


def count() -> int:
    return len(_pool)


async def _sweep_once() -> None:
    now = time.monotonic()
    async with _lock:
        stale = [sid for sid, e in _pool.items() if now - e.last_active > IDLE_SECONDS]
    for sid in stale:
        if await close(sid):
            log.info("Browser-Registry idle geschlossen (session=%s)", sid)


async def _sweeper() -> None:
    while True:
        try:
            await asyncio.sleep(_SWEEP_SECONDS)
            await _sweep_once()
        except asyncio.CancelledError:
            break
        except Exception:
            log.exception("Idle-Sweeper-Fehler")


def start_sweeper() -> None:
    global _sweeper_task
    if _sweeper_task is None or _sweeper_task.done():
        _sweeper_task = asyncio.create_task(_sweeper())


async def stop_sweeper() -> None:
    global _sweeper_task
    if _sweeper_task is not None:
        _sweeper_task.cancel()
        try:
            await _sweeper_task
        except (asyncio.CancelledError, Exception):
            pass
        _sweeper_task = None
