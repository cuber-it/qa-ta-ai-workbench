"""Read and parse the current day's log file for the UI.

Entries are returned incrementally via a byte offset cursor so the frontend can
poll cheaply. Rotation is handled by resetting the cursor when the file is
shorter than the last offset. Lines that do not match the tab-separated format
(e.g. traceback continuations) are appended to the previous entry's message.
"""
from __future__ import annotations

from qataki import paths
from .setup import LOG_FILE

LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]


def _path():
    return paths.logs_dir() / LOG_FILE


def read_recent(pos: int = 0, levels=None, run_id=None, limit: int = 1000):
    """Return new log entries since byte offset ``pos``.

    Returns ``{"entries": [...], "pos": new_offset}``. ``levels`` (list) and
    ``run_id`` (str) filter the result; ``limit`` caps the returned entries.
    """
    p = _path()
    if not p.exists():
        return {"entries": [], "pos": 0}

    size = p.stat().st_size
    if pos > size:  # file rotated or truncated since last poll
        pos = 0

    with open(p, "r", encoding="utf-8", errors="replace") as f:
        f.seek(pos)
        raw = f.read()
        new_pos = f.tell()

    entries: list[dict] = []
    for line in raw.splitlines():
        if not line:
            continue
        parts = line.split("\t", 4)
        if len(parts) == 5:
            ts, level, rid, name, msg = parts
            entries.append({"ts": ts, "level": level, "run": rid, "name": name, "msg": msg})
        elif entries:
            entries[-1]["msg"] += "\n" + line
        else:
            entries.append({"ts": "", "level": "INFO", "run": "-", "name": "", "msg": line})

    if levels:
        want = {lv.upper() for lv in levels}
        entries = [e for e in entries if e["level"] in want]
    if run_id:
        entries = [e for e in entries if e["run"] == run_id]
    if len(entries) > limit:
        entries = entries[-limit:]

    return {"entries": entries, "pos": new_pos}
