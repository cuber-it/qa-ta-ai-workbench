"""
Kontext-Aenderungsprotokoll.

Haelt fest, wer (Mensch/Agent) wann was an Prompts und Skills geaendert hat.
Append-only JSONL unter ``data/context/changelog.jsonl``. Eine Zeile je
Aenderung: ts, actor, action, target, summary, run_id. Bewusst simpel und
unabhaengig — Endpunkte und Agent-Tools rufen nur ``record()``.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime

from . import paths

log = logging.getLogger("qataki.context")

_lock = threading.Lock()
ACTORS = ("human", "agent")
ACTIONS = ("create", "update", "reset", "delete")


def _path():
    return paths.context_dir() / "changelog.jsonl"


def record(actor: str, action: str, target: str,
           summary: str = "", run_id: str | None = None) -> None:
    """Eine Aenderung protokollieren. Wirft nie (Protokoll darf nichts blockieren)."""
    try:
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "actor": actor if actor in ACTORS else "human",
            "action": action,
            "target": target,
            "summary": (summary or "")[:300],
            "run_id": run_id or "",
        }
        p = _path()
        with _lock:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        log.debug("Changelog-Schreibfehler", exc_info=True)


def read(limit: int = 200) -> list[dict]:
    """Letzte ``limit`` Eintraege, neueste zuerst."""
    p = _path()
    if not p.exists():
        return []
    out: list[dict] = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    except Exception:  # noqa: BLE001
        return []
    out.reverse()
    return out[:limit]
