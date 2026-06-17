"""
Projekt-Registry (einfacher JSON-Store).

Ein Projekt gruppiert Agent-Runs (Sessions). Persistenz in data/projects.json.
Runs selbst liegen weiter als Session-JSONL; die Zuordnung steht in der
project_id im Session-Meta.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STORE = REPO / "data" / "projects.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_raw() -> dict:
    if STORE.is_file():
        try:
            d = json.loads(STORE.read_text("utf-8"))
            d.setdefault("projects", {})
            return d
        except Exception:
            pass
    return {"projects": {}}


def _save_raw(d: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(d, indent=2, ensure_ascii=False), "utf-8")


def list_projects() -> list[dict]:
    d = _load_raw()
    items = [{"id": pid, **meta} for pid, meta in d["projects"].items()]
    return sorted(items, key=lambda p: p.get("created_at", ""))


def create_project(name: str, base_url: str = "", description: str = "",
                   artifacts_path: str = "", default_provider: str = "") -> dict:
    d = _load_raw()
    pid = uuid.uuid4().hex
    meta = {
        "name": (name or "").strip() or "Projekt",
        "created_at": _now(),
        "base_url": (base_url or "").strip(),
        "description": (description or "").strip(),
        "artifacts_path": (artifacts_path or "").strip(),
        "default_provider": (default_provider or "").strip(),
    }
    d["projects"][pid] = meta
    _save_raw(d)
    return {"id": pid, **meta}


def rename_project(pid: str, name: str) -> bool:
    d = _load_raw()
    if pid not in d["projects"]:
        return False
    new = (name or "").strip()
    if new:
        d["projects"][pid]["name"] = new
        _save_raw(d)
    return True


def delete_project(pid: str) -> bool:
    d = _load_raw()
    if d["projects"].pop(pid, None) is None:
        return False
    _save_raw(d)
    return True


def exists(pid: str) -> bool:
    return pid in _load_raw()["projects"]


def get_project(pid: str) -> dict | None:
    meta = _load_raw()["projects"].get(pid)
    return {"id": pid, **meta} if meta else None
