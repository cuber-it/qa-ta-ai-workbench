"""
Killswitch / Emergency-Stop — sofortiger Not-Aus für alle LLM-Calls.

Auslösen, wenn ein Agent Amok läuft. Persistent: das Flag bleibt über
Neustarts aktiv, bis es explizit aufgehoben wird. Jeder LLM-Call prüft
`is_active()` und verweigert sofort, solange der Stop steht.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone

log = logging.getLogger("qataki.killswitch")


from . import paths

_FLAG_PATH  = paths.data_dir() / "emergency_stop.flag"
_AUDIT_PATH = paths.logs_dir() / "cost_audit.jsonl"
_LOCK = threading.Lock()


def is_active() -> bool:
    """True solange der Not-Aus steht."""
    return _FLAG_PATH.exists()


def trigger(reason: str = "manual") -> dict:
    """Löst den Not-Aus aus. Ab sofort wird jeder LLM-Call verweigert."""
    info = {
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        "reason":       reason,
    }
    with _LOCK:
        _FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _FLAG_PATH.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    log.error("!!! EMERGENCY STOP — alle LLM-Calls gesperrt (reason=%s) !!!", reason)
    _audit("emergency_stop", {"reason": reason})
    return {"status": "stopped", **info}


def resume() -> dict:
    """Hebt den Not-Aus auf."""
    with _LOCK:
        existed = _FLAG_PATH.exists()
        if existed:
            _FLAG_PATH.unlink()
    log.warning("Emergency stop AUFGEHOBEN (war aktiv: %s)", existed)
    _audit("emergency_resume", {"was_active": existed})
    return {"status": "resumed", "was_active": existed}


def status() -> dict:
    """Aktueller Stand inkl. Auslöse-Info."""
    active = is_active()
    info: dict = {}
    if active:
        try:
            info = json.loads(_FLAG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"active": active, **info}


def _audit(event: str, data: dict) -> None:
    try:
        _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _AUDIT_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts":    datetime.now(timezone.utc).isoformat(),
                "event": event,
                **data,
            }, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("killswitch audit failed: %s", e)
