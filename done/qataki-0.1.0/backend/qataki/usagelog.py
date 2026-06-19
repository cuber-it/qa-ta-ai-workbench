"""
Token-Verbrauchslog.

Schreibt pro LLM-Call eine Zeile (TSV) nach ``logs/token-usage.log``:

    ts<TAB>run_id<TAB>provider<TAB>model<TAB>input<TAB>output

Append-only, eine Zeile je Call, mit Sekunden-Zeitstempel (lokale Zeit, ISO).
Zur Laufzeit ueber ``set_enabled()`` an/aus schaltbar; Default aktiviert. Ist es
aus, ist ``record()`` ein No-Op. Bewusst simpel: gut mit awk/Excel auswertbar,
ideal um den gemeldeten Verbrauch gegen die Provider-Abrechnung zu pruefen.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime

from . import paths

log = logging.getLogger("qataki.usagelog")

_COLS = ("ts", "run_id", "provider", "model", "input", "output")
_HEADER = "\t".join(_COLS) + "\n"
_enabled = True
_lock = threading.Lock()


def _path():
    return paths.logs_dir() / "token-usage.log"


def set_enabled(on: bool) -> None:
    """Logging zur Laufzeit an/aus. Wirkt sofort fuer folgende Calls."""
    global _enabled
    _enabled = bool(on)
    log.info("Token-Verbrauchslog %s", "aktiviert" if _enabled else "deaktiviert")


def is_enabled() -> bool:
    return _enabled


def record(run_id: str, provider: str, model: str,
           input_tokens: int, output_tokens: int) -> None:
    """Eine Verbrauchszeile anhaengen. No-Op wenn deaktiviert. Wirft nie."""
    if not _enabled:
        return
    try:
        p = _path()
        line = (f"{datetime.now().isoformat(timespec='seconds')}\t{run_id}\t"
                f"{provider}\t{model}\t{int(input_tokens)}\t{int(output_tokens)}\n")
        with _lock:
            new = not p.exists()
            with open(p, "a", encoding="utf-8") as fh:
                if new:
                    fh.write(_HEADER)
                fh.write(line)
    except Exception:  # noqa: BLE001 — Logging darf den Lauf nie stoppen
        log.debug("Token-Verbrauchslog Schreibfehler", exc_info=True)


def read_recent(limit: int = 500) -> dict:
    """Die letzten ``limit`` Eintraege + Summen, fuer die UI. Robust gegen das
    alte 5-Spalten-Format (ohne provider) und fehlende Datei."""
    p = _path()
    entries: list[dict] = []
    if p.exists():
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except Exception:  # noqa: BLE001
            lines = []
        for ln in lines:
            if not ln.strip() or ln.startswith("ts\t"):
                continue
            f = ln.split("\t")
            # Neu: ts,run,provider,model,in,out | Alt: ts,run,model,in,out
            if len(f) >= 6:
                ts, run, provider, model, inp, out = f[0], f[1], f[2], f[3], f[4], f[5]
            elif len(f) == 5:
                ts, run, provider, model, inp, out = f[0], f[1], "", f[2], f[3], f[4]
            else:
                continue
            try:
                inp_i, out_i = int(inp), int(out)
            except ValueError:
                continue
            entries.append({"ts": ts, "run": run, "provider": provider,
                            "model": model, "input": inp_i, "output": out_i})
    total_all = len(entries)
    # Summen ueber ALLE Calls (nicht nur die angezeigten) — fuer den Abgleich.
    tot_in = sum(e["input"] for e in entries)
    tot_out = sum(e["output"] for e in entries)
    if limit and len(entries) > limit:
        entries = entries[-limit:]
    return {
        "entries": entries,
        "totals": {"calls": total_all, "input": tot_in, "output": tot_out,
                   "total": tot_in + tot_out},
        "enabled": _enabled,
    }


def path_str() -> str:
    return str(_path())
