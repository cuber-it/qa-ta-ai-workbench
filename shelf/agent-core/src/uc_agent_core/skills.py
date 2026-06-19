"""
SkillRegistry — Markdown-Prozeduren, die der Agent bei Bedarf laedt.

Ein Skill ist ein Ordner <name>/SKILL.md mit Frontmatter (name, when_to_use)
und einer Schritt-fuer-Schritt-Anleitung im Body. Der Katalog (Name + Zweck)
liegt im Systemprompt; den vollen Body laedt der Agent on-demand ueber
skill__load (progressive disclosure).

Zwei Ebenen: Werks-Defaults im Paket (``skills/``, versioniert) und ein
optionaler Override-Ordner (vom Host via ``set_override_dir`` gesetzt, unter
``home/``). Override hat Vorrang; ein dort liegender Skill mit gleichem Ordner-
namen ueberlagert den Default ("override"), ein neuer ist "custom". Defaults
bleiben unangetastet -> jede Anpassung ist zuruecksetzbar. Reine Stdlib.
"""
from __future__ import annotations

import re
from pathlib import Path

_SKILLS_DIR = Path(__file__).resolve().parent / "skills"   # Werks-Defaults (Paket)
_override_dir: Path | None = None                          # vom Host gesetzt (home/...)

_SAFE_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def set_override_dir(path) -> None:
    global _override_dir
    _override_dir = Path(path) if path else None


def _safe_key(key: str) -> str:
    k = (key or "").strip().lower().replace(" ", "-")
    if not _SAFE_KEY.match(k):
        raise ValueError(f"Ungueltiger Skill-Name '{key}' (erlaubt: a-z 0-9 - _)")
    return k


safe_key = _safe_key  # oeffentlicher Alias


def _norm(key: str) -> str | None:
    """Sicherer Key oder None (statt Exception) — fuer lesende Zugriffe."""
    try:
        return _safe_key(key)
    except ValueError:
        return None


def _parse(md: str) -> tuple[dict, str]:
    """Trennt optionales ----Frontmatter vom Body."""
    meta: dict = {}
    body = md
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            front = md[3:end].strip()
            body = md[end + 4:].lstrip("\n")
            for line in front.splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip()
    return meta, body


def _read_dir(base: Path | None) -> dict[str, tuple[dict, str]]:
    res: dict[str, tuple[dict, str]] = {}
    if base and base.is_dir():
        for d in sorted(base.iterdir()):
            f = d / "SKILL.md"
            if f.is_file():
                res[d.name] = _parse(f.read_text(encoding="utf-8"))
    return res


def list_skills() -> list[dict]:
    """Gemergte Liste. ``source``: default | override | custom."""
    pkg = _read_dir(_SKILLS_DIR)
    ovr = _read_dir(_override_dir)
    out: list[dict] = []
    for key in sorted(set(pkg) | set(ovr)):
        meta = (ovr.get(key) or pkg.get(key))[0]
        source = "override" if key in ovr and key in pkg else ("custom" if key in ovr else "default")
        out.append({"key": key, "name": meta.get("name", key),
                    "when_to_use": meta.get("when_to_use", ""), "source": source})
    return out


def load_skill(name: str) -> str | None:
    """Body eines Skills (per Frontmatter-Name oder Ordnername). Override vor Default."""
    for base in (_override_dir, _SKILLS_DIR):
        if base is None or not base.is_dir():
            continue
        for d in base.iterdir():
            f = d / "SKILL.md"
            if not f.is_file():
                continue
            meta, body = _parse(f.read_text(encoding="utf-8"))
            if meta.get("name") == name or d.name == name:
                return body
    return None


def read_raw(key: str) -> str | None:
    """Voller SKILL.md-Text (mit Frontmatter), Override vor Default — fuer den Editor."""
    k = _norm(key)
    if not k:
        return None
    for base in (_override_dir, _SKILLS_DIR):
        if base is None:
            continue
        f = base / k / "SKILL.md"
        if f.is_file():
            return f.read_text(encoding="utf-8")
    return None


def default_raw(key: str) -> str | None:
    k = _norm(key)
    if not k:
        return None
    f = _SKILLS_DIR / k / "SKILL.md"
    return f.read_text(encoding="utf-8") if f.is_file() else None


def has_default(key: str) -> bool:
    k = _norm(key)
    return bool(k) and (_SKILLS_DIR / k / "SKILL.md").is_file()


def save_skill(key: str, content: str) -> str:
    """Skill in den Override-Ordner schreiben. Gibt den (sicheren) Key zurueck."""
    if _override_dir is None:
        raise RuntimeError("Kein Override-Verzeichnis gesetzt")
    k = _safe_key(key)
    d = _override_dir / k
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(content, encoding="utf-8")
    return k


def remove_override(key: str) -> bool:
    """Override/Custom-Skill entfernen. True, wenn etwas geloescht wurde.
    Liegt ein Paket-Default vor, greift dieser danach wieder."""
    if _override_dir is None:
        return False
    k = _safe_key(key)
    f = _override_dir / k / "SKILL.md"
    if f.is_file():
        f.unlink()
        try:
            (_override_dir / k).rmdir()
        except OSError:
            pass
        return True
    return False


def catalog_text() -> str:
    """Kurzer Katalog fuer den Systemprompt."""
    skills = list_skills()
    if not skills:
        return ""
    lines = ["Verfuegbare Skills (volle Anleitung per skill__load laden):"]
    for s in skills:
        lines.append(f"- {s['name']}: {s['when_to_use']}")
    return "\n".join(lines)
