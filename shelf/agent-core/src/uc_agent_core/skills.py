"""
SkillRegistry — Markdown-Prozeduren, die der Agent bei Bedarf laedt.

Ein Skill ist ein Ordner agent/skills/<name>/SKILL.md mit Frontmatter
(name, when_to_use) und einer Schritt-fuer-Schritt-Anleitung im Body.
Der Katalog (Name + Einsatzzweck) wird dem Agenten in den Systemprompt
gelegt; den vollen Body laedt er on-demand ueber das Tool skill__load
(progressive disclosure).

Reine Stdlib, keine Projekt-Abhaengigkeiten -> mit dem Framework-Kern
extrahierbar.
"""
from __future__ import annotations

from pathlib import Path

_SKILLS_DIR = Path(__file__).resolve().parent / "skills"


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


def list_skills() -> list[dict]:
    out: list[dict] = []
    if not _SKILLS_DIR.is_dir():
        return out
    for d in sorted(_SKILLS_DIR.iterdir()):
        f = d / "SKILL.md"
        if f.is_file():
            meta, _ = _parse(f.read_text(encoding="utf-8"))
            out.append({"name": meta.get("name", d.name),
                        "when_to_use": meta.get("when_to_use", "")})
    return out


def load_skill(name: str) -> str | None:
    """Body eines Skills (per Frontmatter-Name oder Ordnername)."""
    if not _SKILLS_DIR.is_dir():
        return None
    for d in _SKILLS_DIR.iterdir():
        f = d / "SKILL.md"
        if not f.is_file():
            continue
        meta, body = _parse(f.read_text(encoding="utf-8"))
        if meta.get("name") == name or d.name == name:
            return body
    return None


def catalog_text() -> str:
    """Kurzer Katalog fuer den Systemprompt."""
    skills = list_skills()
    if not skills:
        return ""
    lines = ["Verfuegbare Skills (volle Anleitung per skill__load laden):"]
    for s in skills:
        lines.append(f"- {s['name']}: {s['when_to_use']}")
    return "\n".join(lines)
