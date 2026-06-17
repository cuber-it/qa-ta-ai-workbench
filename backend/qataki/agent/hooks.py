"""
Guardrails-Hooks — Erweiterungspunkt um die Tool-Ausfuehrung.

tool_guards: Liste von Callables (name, args) -> str | None.
Gibt ein Guard einen Grund-String zurueck, wird der Tool-Aufruf NICHT
ausgefuehrt; der Grund geht als Fehler-Ergebnis ans LLM zurueck, das sich
darauf einstellen kann. Default: keine Guards (alles erlaubt).

Reine Stdlib -> mit dem Framework-Kern extrahierbar.
"""
from __future__ import annotations

from typing import Callable, Optional

ToolGuard = Callable[[str, dict], Optional[str]]

# Aktive Guards (leer = alles erlaubt). Zur Laufzeit befuellbar.
tool_guards: list[ToolGuard] = []


def check_tool(name: str, args: dict) -> str | None:
    """Erster Guard, der einen Grund liefert, blockt; sonst None."""
    for g in tool_guards:
        try:
            reason = g(name, args or {})
        except Exception as e:  # noqa: BLE001
            reason = f"Guard-Fehler: {e}"
        if reason:
            return reason
    return None


def deny_tools(*names: str) -> ToolGuard:
    """Fertiger Guard: blockt die genannten Tool-Namen."""
    blocked = set(names)

    def _guard(name: str, args: dict) -> str | None:
        if name in blocked:
            return f"Tool '{name}' ist per Guardrail gesperrt."
        return None

    return _guard
