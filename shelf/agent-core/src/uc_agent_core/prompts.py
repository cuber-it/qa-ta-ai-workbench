"""
Prompt-Dateien — editierbar, nicht im Code vergraben.

load_prompt("system") liest agent/prompts/system.md. Reine Stdlib.
"""
from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> str:
    f = _PROMPTS_DIR / f"{name}.md"
    return f.read_text(encoding="utf-8").strip() if f.is_file() else ""
