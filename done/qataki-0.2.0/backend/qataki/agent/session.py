"""
Session — Gedaechtnis/Kontext + Protokoll im Claude-Code-Stil.

Jede Session hat eine ID, einen Nachrichten-Verlauf (= Kontext fuer das LLM)
und ein append-only Protokoll als JSONL unter data/sessions/{id}.jsonl. Jede
Zeile ist ein Event (session|user|assistant|tool_use|tool_result|system|
final|error|note) mit Zeitstempel. Resumebar: load() spielt das Protokoll
zurueck in den Nachrichten-Verlauf.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from uc_llm_provider import ChatMessage
from uc_llm_provider.core.models import ToolResultBlock

from .. import paths

# Anker ueber paths (ehrt QATAKI_HOME) statt .git-Walk -> konsistent mit
# config/projects/settings/artifacts, alles unter einem home/data.
_SESS_DIR = paths.sessions_dir()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Session:
    def __init__(self, session_id: str, title: str = ""):
        self.id = session_id
        self.title = title
        self.created_at = _now()
        self.messages: list = []   # uc_llm_provider Message/ChatMessage-Objekte
        self.project_id = ""
        self.run = {}
        self._path = _SESS_DIR / f"{session_id}.jsonl"

    # ── Persistenz ──────────────────────────────────────────────────────────
    def _append(self, event: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": _now(), **event}
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    # ── Erzeugen / Laden ────────────────────────────────────────────────────
    @classmethod
    def create(cls, title: str = "", project_id: str = "", *, url: str = "",
               provider: str = "", headless: bool = True, description: str = "",
               artifacts_path: str = "", model: str = "", temperature: str = "") -> "Session":
        s = cls(uuid.uuid4().hex, title)
        s.project_id = project_id
        s.run = {"url": url, "provider": provider, "headless": headless,
                 "description": description, "artifacts_path": artifacts_path,
                 "model": model, "temperature": temperature}
        s._append({"type": "session", "session_id": s.id, "created_at": s.created_at,
                   "title": title, "project_id": project_id,
                   "url": url, "provider": provider, "headless": headless,
                   "description": description, "artifacts_path": artifacts_path,
                   "model": model, "temperature": temperature})
        return s

    @classmethod
    def load(cls, session_id: str) -> "Session":
        path = _SESS_DIR / f"{session_id}.jsonl"
        if not path.exists():
            raise KeyError(session_id)
        s = cls(session_id)
        pending: list = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            ev = json.loads(line)
            t = ev.get("type")
            if t == "session":
                s.created_at = ev.get("created_at", s.created_at)
                s.title = ev.get("title", "")
                s.project_id = ev.get("project_id", "")
                s.run = {"url": ev.get("url", ""), "provider": ev.get("provider", ""),
                         "headless": ev.get("headless", True),
                         "description": ev.get("description", ""),
                         "artifacts_path": ev.get("artifacts_path", ""),
                         "model": ev.get("model", ""),
                         "temperature": ev.get("temperature", "")}
            elif t == "user":
                s._flush(pending)
                s.messages.append(ChatMessage(role="user", content=ev["text"]))
            elif t == "assistant":
                s._flush(pending)
                s.messages.append(ChatMessage(role="assistant", content=ev["content"]))
            elif t == "tool_result":
                pending.append(ToolResultBlock(
                    tool_use_id=ev["tool_use_id"],
                    content=ev.get("content", ""),
                    is_error=ev.get("is_error", False),
                ))
            # tool_use / system / final / error / note: nur Protokoll, kein Verlauf
        s._flush(pending)
        s._repair_tool_calls()
        return s

    def _flush(self, pending: list) -> None:
        if pending:
            self.messages.append(ChatMessage(role="user", content=list(pending)))
            pending.clear()

    @staticmethod
    def _blocks(m) -> list:
        return m.content if isinstance(m.content, list) else []

    @staticmethod
    def _btype(b):
        return b.get("type") if isinstance(b, dict) else getattr(b, "type", None)

    def _tool_use_ids(self, m) -> list:
        if getattr(m, "role", None) != "assistant":
            return []
        out = []
        for b in self._blocks(m):
            if self._btype(b) == "tool_use":
                bid = b.get("id") if isinstance(b, dict) else getattr(b, "id", None)
                if bid:
                    out.append(bid)
        return out

    def _tool_result_ids(self, m) -> set:
        if getattr(m, "role", None) != "user":
            return set()
        out = set()
        for b in self._blocks(m):
            tid = b.get("tool_use_id") if isinstance(b, dict) else getattr(b, "tool_use_id", None)
            if tid:
                out.add(tid)
        return out

    def _repair_tool_calls(self) -> None:
        """Sichert die API-Invariante: jede Assistant-Nachricht mit tool_use wird
        von tool_result-Nachrichten fuer JEDE id gefolgt. Fehlende (z. B. durch
        einen abgebrochenen Lauf) werden mit einem synthetischen Ergebnis ergaenzt,
        damit ein erneuter Call nicht an unbeantworteten tool_call_ids scheitert."""
        msgs = self.messages
        repaired: list = []
        for i, m in enumerate(msgs):
            repaired.append(m)
            ids = self._tool_use_ids(m)
            if not ids:
                continue
            answered = self._tool_result_ids(msgs[i + 1]) if i + 1 < len(msgs) else set()
            missing = [t for t in ids if t not in answered]
            if missing:
                synth = [ToolResultBlock(
                    tool_use_id=t,
                    content="(kein Ergebnis — Lauf wurde unterbrochen)",
                    is_error=True,
                ) for t in missing]
                repaired.append(ChatMessage(role="user", content=synth))
        self.messages = repaired

    # ── Verlauf erweitern (Verlauf + Protokoll) ─────────────────────────────
    def add_user(self, text: str) -> None:
        self.messages.append(ChatMessage(role="user", content=text))
        self._append({"type": "user", "text": text})

    def add_assistant(self, content) -> None:
        """content: list[Block] (Text/ToolUse) oder str."""
        self.messages.append(ChatMessage(role="assistant", content=content))
        if isinstance(content, str):
            dumped = content
        else:
            dumped = [b.model_dump() if hasattr(b, "model_dump") else b for b in content]
        self._append({"type": "assistant", "content": dumped})
        if not isinstance(content, str):
            for b in content:
                if getattr(b, "type", None) == "tool_use":
                    self._append({"type": "tool_use", "id": b.id,
                                  "name": b.name, "input": b.input})

    def add_tool_results(self, results: list) -> None:
        """results: list[ToolResultBlock]."""
        self.messages.append(ChatMessage(role="user", content=list(results)))
        for r in results:
            self._append({"type": "tool_result", "tool_use_id": r.tool_use_id,
                          "content": r.content, "is_error": r.is_error})

    def log(self, kind: str, **payload) -> None:
        """Protokoll-only Event (system|final|error|note)."""
        self._append({"type": kind, **payload})

    def to_messages(self) -> list:
        return self.messages

    def artifact_dir(self) -> Path:
        """Ordner fuer Artefakte dieses Runs: <basis>/<run-id> ('~' expandiert)."""
        base = (self.run.get("artifacts_path") or "").strip() or "~/.qataki"
        return Path(base).expanduser() / self.id


# ── Verzeichnis ─────────────────────────────────────────────────────────────
def list_sessions(project_id: str | None = None) -> list[dict]:
    if not _SESS_DIR.exists():
        return []
    out = []
    for p in sorted(_SESS_DIR.glob("*.jsonl")):
        meta = {"id": p.stem, "title": "", "created_at": None, "events": 0, "project_id": "",
                "url": "", "provider": "", "model": "", "temperature": "", "description": "", "headless": True,
                "artifacts_path": ""}
        try:
            lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
            meta["events"] = len(lines)
            if lines:
                first = json.loads(lines[0])
                meta["created_at"] = first.get("created_at")
                meta["title"] = first.get("title", "")
                meta["project_id"] = first.get("project_id", "")
                meta["url"] = first.get("url", "")
                meta["provider"] = first.get("provider", "")
                meta["model"] = first.get("model", "")
                meta["temperature"] = first.get("temperature", "")
                meta["description"] = first.get("description", "")
                meta["headless"] = first.get("headless", True)
                meta["artifacts_path"] = first.get("artifacts_path", "")
        except Exception:
            pass
        if project_id is not None and meta["project_id"] != project_id:
            continue
        out.append(meta)
    return out


def read_protocol(session_id: str) -> list[dict]:
    """Alle Protokoll-Events einer Session (JSONL -> Liste)."""
    path = _SESS_DIR / f"{session_id}.jsonl"
    if not path.exists():
        raise KeyError(session_id)
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def delete_session(session_id: str) -> bool:
    path = _SESS_DIR / f"{session_id}.jsonl"
    if path.exists():
        path.unlink()
        return True
    return False


def rename_session(session_id: str, title: str) -> bool:
    """Titel einer Session aendern (steht im ersten Event = erste JSONL-Zeile)."""
    path = _SESS_DIR / f"{session_id}.jsonl"
    if not path.exists():
        return False
    new = (title or "").strip()
    if not new:
        return True
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        return False
    first = json.loads(lines[0])
    first["title"] = new
    lines[0] = json.dumps(first, ensure_ascii=False, default=str)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


_EDITABLE = ("title", "url", "provider", "model", "temperature", "description", "headless", "artifacts_path")


def update_session(session_id: str, fields: dict) -> bool:
    """Whitelisted Meta-Felder einer Session aendern (steht im ersten Event)."""
    path = _SESS_DIR / f"{session_id}.jsonl"
    if not path.exists():
        return False
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        return False
    first = json.loads(lines[0])
    for k in _EDITABLE:
        if k in fields and fields[k] is not None:
            v = fields[k]
            if isinstance(v, str):
                v = v.strip()
                if k == "title" and not v:
                    continue   # leeren Titel nicht uebernehmen
            first[k] = v
    lines[0] = json.dumps(first, ensure_ascii=False, default=str)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True
