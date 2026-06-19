"""
Prompt-Dateien — editierbar, nicht im Code vergraben.

Zwei Ebenen: Werks-Defaults liegen im Paket (``prompts/<name>.md``, versioniert).
Ein optionaler Override-Ordner (vom Host via ``set_override_dir`` gesetzt, liegt
unter ``home/``) hat Vorrang. So bleibt der Paketcode unangetastet und jede
Anpassung ist jederzeit auf Default zuruecksetzbar. Reine Stdlib.
"""
from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"   # Werks-Default (Paket)
_override_dir: Path | None = None                            # vom Host gesetzt (home/...)


def set_override_dir(path) -> None:
    """Verzeichnis fuer benutzer-editierte Prompts. None = nur Defaults."""
    global _override_dir
    _override_dir = Path(path) if path else None


def _override_file(name: str) -> Path | None:
    return (_override_dir / f"{name}.md") if _override_dir is not None else None


def load_prompt(name: str) -> str:
    """Wirksamer Prompt: Override vor Default."""
    ov = _override_file(name)
    if ov is not None and ov.is_file():
        return ov.read_text(encoding="utf-8").strip()
    f = _PROMPTS_DIR / f"{name}.md"
    return f.read_text(encoding="utf-8").strip() if f.is_file() else ""


def default_prompt(name: str) -> str:
    """Werks-Default (Paket), ignoriert Override — fuer 'Auf Default zuruecksetzen'."""
    f = _PROMPTS_DIR / f"{name}.md"
    return f.read_text(encoding="utf-8").strip() if f.is_file() else ""


def is_overridden(name: str) -> bool:
    ov = _override_file(name)
    return ov is not None and ov.is_file()


def save_override(name: str, content: str) -> None:
    if _override_dir is None:
        raise RuntimeError("Kein Override-Verzeichnis gesetzt")
    _override_dir.mkdir(parents=True, exist_ok=True)
    (_override_dir / f"{name}.md").write_text(content, encoding="utf-8")


def reset_override(name: str) -> bool:
    """Override entfernen -> Default greift wieder. True, wenn etwas geloescht wurde."""
    ov = _override_file(name)
    if ov is not None and ov.is_file():
        ov.unlink()
        return True
    return False
