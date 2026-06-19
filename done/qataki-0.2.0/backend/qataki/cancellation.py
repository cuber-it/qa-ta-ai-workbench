"""
In-Flight-Cancellation — bricht laufende LLM-Calls bei NOTAUS ab.

Jeder LLM-Call laeuft als registrierte asyncio.Task. kill_all() canceled
alle offenen Tasks -> CancelledError propagiert in httpx -> die
HTTP-Verbindung zum Provider wird gekappt.

Hintergrund: Fuer interaktive Calls gibt es bei OpenAI/Anthropic keinen
serverseitigen "Cancel-Request"-Endpunkt (nur fuer Batch-Jobs). Der einzige
echte Abbruch eines laufenden Calls ist clientseitig das Kappen der
Verbindung. Ein Abbruch begrenzt die Kosten, garantiert aber nicht null:
bereits serverseitig erzeugte Tokens koennen berechnet werden (von den
Anbietern bestaetigt).

Verifiziert (06/2026): OpenAI bietet einen serverseitigen Cancel NUR fuer
Responses mit background=true; Anthropic nur clientseitigen Stream-Abbruch.
Fuer lange Agent-Runs koennte spaeter der OpenAI-Background-Mode einen
echten Server-Kill liefern -- offene Option, hier noch nicht genutzt.
"""
from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("qataki.cancellation")

_inflight: set[asyncio.Task] = set()


async def run(coro):
    """Fuehrt coro als getrackte Task aus, damit NOTAUS sie abbrechen kann."""
    task = asyncio.ensure_future(coro)
    _inflight.add(task)
    task.add_done_callback(_inflight.discard)
    return await task


def kill_all() -> int:
    """Bricht alle laufenden LLM-Calls ab. Muss im Event-Loop-Thread laufen."""
    n = 0
    for task in list(_inflight):
        if not task.done():
            task.cancel()
            n += 1
    if n:
        log.error("Cancellation: %d laufende(r) LLM-Call(s) abgebrochen", n)
    return n


def inflight_count() -> int:
    return sum(1 for t in _inflight if not t.done())
