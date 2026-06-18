"""
ToolRegistry — fuehrt die Tool-Quellen des Agenten zusammen.

Vier Quellen, nach Praefix getrennt:
  pw__*             festverbaute Playwright-Interfaces (uc_playwright_driver-Lib)
  rest__*           festverbaute REST-Kommandos (Platzhalter, kommt spaeter)
  mcp__<server>__*  dynamisch ueber den MCP-Client (konfigurierte Server)
  skill__list/load  eingebaute Skill-Meta-Tools (Markdown-Prozeduren)

Liefert die vereinte ToolDefinition-Liste fuers LLM (tool_specs) und routet
Aufrufe (dispatch). Ein BrowserClient wird pro Registry-Instanz (= pro
Agent-Lauf/Session) lazy erzeugt und am Ende via aclose() geschlossen.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

from uc_llm_provider.core.models import ToolDefinition

from uc_playwright_driver import tools as _pw
from . import skills


class _NullMcp:
    """Default MCP client — no servers. The host injects the real one via set_mcp_client()."""
    def load_config(self):
        return {"servers": {}}
    async def list_tools(self, server):
        return []
    async def call_tool(self, server, tool, arguments):
        return {"content": "MCP nicht konfiguriert.", "is_error": True}


_mcp = _NullMcp()   # injected by the host

_OBJ = {"type": "object", "properties": {}}

# Kuratiertes Playwright-Kernset. fn = uc_playwright_driver-Funktion (client, **kwargs)
_PW_TOOLS: dict[str, dict] = {
    "navigate": {"fn": _pw.navigate, "desc": "Browser zu einer URL navigieren.",
        "schema": {"type": "object", "properties": {
            "url": {"type": "string"},
            "wait_until": {"type": "string", "enum": ["domcontentloaded", "load", "networkidle"], "default": "load"}},
            "required": ["url"]}},
    "get_page_content": {"fn": _pw.get_page_content, "desc": "Sichtbaren Textinhalt der Seite holen.",
        "schema": {"type": "object", "properties": {"max_length": {"type": "integer", "default": 10000}}}},
    "get_text": {"fn": _pw.get_text, "desc": "Text eines Elements per CSS-Selektor.",
        "schema": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}},
    "click_by_text": {"fn": _pw.click_by_text, "desc": "Element mit sichtbarem Text klicken.",
        "schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    "click_by_role": {"fn": _pw.click_by_role, "desc": "Element per ARIA-Rolle (optional Name) klicken.",
        "schema": {"type": "object", "properties": {"role": {"type": "string"}, "name": {"type": "string", "default": ""}}, "required": ["role"]}},
    "fill_by_label": {"fn": _pw.fill_by_label, "desc": "Eingabefeld per Label ausfuellen.",
        "schema": {"type": "object", "properties": {"label": {"type": "string"}, "value": {"type": "string"}}, "required": ["label", "value"]}},
    "fill": {"fn": _pw.fill, "desc": "Eingabefeld per CSS-Selektor ausfuellen.",
        "schema": {"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}}, "required": ["selector", "text"]}},
    "find_by_role": {"fn": _pw.find_by_role, "desc": "Elemente per ARIA-Rolle finden (optional Name).",
        "schema": {"type": "object", "properties": {"role": {"type": "string"}, "name": {"type": "string", "default": ""}}, "required": ["role"]}},
    "get_links": {"fn": _pw.get_links, "desc": "Alle Links der Seite.", "schema": _OBJ},
    "current_url": {"fn": _pw.current_url, "desc": "Aktuelle URL.", "schema": _OBJ},
    "get_title": {"fn": _pw.get_title, "desc": "Seitentitel.", "schema": _OBJ},
    "wait_for": {"fn": _pw.wait_for, "desc": "Auf ein Element (CSS-Selektor) warten.",
        "schema": {"type": "object", "properties": {"selector": {"type": "string"}, "timeout": {"type": "integer", "default": 10000}}, "required": ["selector"]}},
    "press": {"fn": _pw.press, "desc": "Taste druecken (optional in einem Element).",
        "schema": {"type": "object", "properties": {"key": {"type": "string"}, "selector": {"type": "string", "default": ""}}, "required": ["key"]}},
}


class ToolRegistry:
    def __init__(self, headless: bool = True, artifacts_path: str = ""):
        self._browser = None
        self._headless = headless
        self._artifacts_path = artifacts_path

    # ── Playwright-Browser (lazy, pro Registry) ─────────────────────────────
    async def _pw_client(self):
        if self._browser is None:
            from uc_playwright_driver.client import BrowserClient
            self._browser = BrowserClient({"headless": self._headless, "timeout": 20000})
        return self._browser

    async def aclose(self) -> None:
        if self._browser is not None:
            try:
                await self._browser.cleanup()
            except Exception:
                pass
            self._browser = None

    # ── Specs fuers LLM ─────────────────────────────────────────────────────
    async def tool_specs(self) -> list[ToolDefinition]:
        specs: list[ToolDefinition] = []
        for name, t in _PW_TOOLS.items():
            specs.append(ToolDefinition(name=f"pw__{name}", description=t["desc"], input_schema=t["schema"]))
        # Screenshot schreibt direkt in den Artefakt-Ordner des Runs. Mit url wird
        # vorher dorthin navigiert (nav+shot in einem Aufruf), sonst aktuelle Seite.
        specs.append(ToolDefinition(name="pw__screenshot",
            description=("Screenshot als PNG im Artefakt-Ordner des Runs speichern. Ohne "
                         "url wird die aktuelle Seite geknipst; mit url wird zuerst dorthin "
                         "navigiert und dann geknipst — fuer mehrere Seiten pro Seite ein "
                         "Aufruf mit url."),
            input_schema={"type": "object", "properties": {
                "filename": {"type": "string", "description": "relativer PNG-Dateiname, z. B. 01-startseite.png"},
                "url": {"type": "string", "description": "optional: vorher hierhin navigieren, dann knipsen"},
                "full_page": {"type": "boolean", "default": True, "description": "ganze Seite statt nur Viewport"}},
                "required": ["filename"]}))
        # Skill-Meta-Tools (eingebaut)
        specs.append(ToolDefinition(name="skill__list",
            description="Listet verfuegbare Skills mit Einsatzzweck.", input_schema=_OBJ))
        specs.append(ToolDefinition(name="skill__load",
            description="Laedt die Schritt-fuer-Schritt-Anleitung eines Skills.",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}))
        # Artefakt-Tools (schreiben in den Run-Ordner)
        specs.append(ToolDefinition(name="artifact__save",
            description="Speichert ein Artefakt (z. B. eine .feature-Datei) im Artefakt-Ordner des Runs.",
            input_schema={"type": "object", "properties": {
                "filename": {"type": "string", "description": "relativer Dateiname, z. B. login.feature"},
                "content": {"type": "string"}}, "required": ["filename", "content"]}))
        specs.append(ToolDefinition(name="artifact__list",
            description="Listet die bereits im Run-Ordner gespeicherten Artefakte.", input_schema=_OBJ))
        # rest__* — Platzhalter, noch keine Tools
        cfg = _mcp.load_config()
        for server in cfg.get("servers", {}):
            try:
                for tl in await _mcp.list_tools(server):
                    specs.append(ToolDefinition(
                        name=f"mcp__{server}__{tl['name']}",
                        description=tl.get("description", ""),
                        input_schema=tl.get("input_schema") or {"type": "object", "properties": {}}))
            except Exception:
                continue  # nicht erreichbarer Server blockiert die Liste nicht
        return specs

    # ── Dispatch ────────────────────────────────────────────────────────────
    async def dispatch(self, name: str, arguments: dict | None) -> tuple[str, bool]:
        """Gibt (content, is_error) zurueck."""
        arguments = arguments or {}
        try:
            if name.startswith("skill__"):
                return await self._dispatch_skill(name, arguments)
            if name.startswith("artifact__"):
                return await self._dispatch_artifact(name, arguments)
            if name.startswith("pw__"):
                return await self._dispatch_pw(name[4:], arguments)
            if name.startswith("mcp__"):
                return await self._dispatch_mcp(name[5:], arguments)
            if name.startswith("rest__"):
                return ("REST-Tools sind noch nicht verfuegbar.", True)
            return (f"Unbekanntes Tool: {name}", True)
        except Exception as e:  # noqa: BLE001
            return (f"Tool-Fehler ({name}): {e}", True)

    async def _dispatch_skill(self, name: str, arguments: dict) -> tuple[str, bool]:
        if name == "skill__list":
            return (json.dumps(skills.list_skills(), ensure_ascii=False), False)
        if name == "skill__load":
            sk = (arguments or {}).get("name", "")
            body = skills.load_skill(sk)
            if body is None:
                return (f"Skill nicht gefunden: {sk}", True)
            return (body, False)
        return (f"Unbekanntes Skill-Tool: {name}", True)

    def _run_dir(self) -> tuple[Path | None, str | None]:
        """Artefakt-Basisordner dieses Runs ('~' expandiert) oder Fehlertext."""
        base = (self._artifacts_path or "").strip()
        if not base:
            return (None, "Kein Artefakt-Ordner fuer diesen Run konfiguriert.")
        return (Path(base).expanduser(), None)

    def _resolve_artifact(self, filename: str, ext: str | None = None) -> tuple[Path | None, str | None]:
        """Relativen Dateinamen sicher in den Run-Ordner aufloesen.

        Kein absoluter Pfad, kein '..'; legt den Zielordner an. Optional wird eine
        Endung erzwungen (z. B. '.png'). Gemeinsame Basis fuer artifact__save und den
        Screenshot — beide schreiben in denselben Run-Ordner.
        """
        base_p, err = self._run_dir()
        if err:
            return (None, err)
        fn = (filename or "").strip()
        if not fn:
            return (None, "filename fehlt.")
        if ext and not fn.lower().endswith(ext):
            fn += ext
        rel = Path(fn)
        if rel.is_absolute() or ".." in rel.parts:
            return (None, "Ungueltiger Dateiname (kein absoluter Pfad, kein '..').")
        target = base_p / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        return (target, None)

    async def _dispatch_artifact(self, name: str, arguments: dict) -> tuple[str, bool]:
        base_p, err = self._run_dir()
        if err:
            return (err, True)
        if name == "artifact__list":
            if not base_p.exists():
                return ("(noch keine Artefakte)", False)
            files = sorted(str(p.relative_to(base_p)) for p in base_p.rglob("*") if p.is_file())
            return (json.dumps(files, ensure_ascii=False) if files else "(noch keine Artefakte)", False)
        if name == "artifact__save":
            target, err = self._resolve_artifact(arguments.get("filename"))
            if err:
                return (err, True)
            content = arguments.get("content", "")
            text = content if isinstance(content, str) else str(content)
            target.write_text(text, encoding="utf-8")
            return (f"Gespeichert: {target} ({len(text)} Zeichen)", False)
        return (f"Unbekanntes Artefakt-Tool: {name}", True)

    async def _dispatch_pw(self, fn_name: str, arguments: dict) -> tuple[str, bool]:
        if fn_name == "screenshot":
            return await self._dispatch_screenshot(arguments)
        t = _PW_TOOLS.get(fn_name)
        if not t:
            return (f"Unbekanntes Playwright-Tool: pw.{fn_name}", True)
        client = await self._pw_client()
        params = set(inspect.signature(t["fn"]).parameters) - {"client"}
        kwargs = {k: v for k, v in arguments.items() if k in params}
        result = await t["fn"](client, **kwargs)
        return (str(result), False)

    async def _dispatch_screenshot(self, arguments: dict) -> tuple[str, bool]:
        target, err = self._resolve_artifact(arguments.get("filename"), ext=".png")
        if err:
            return (err, True)
        client = await self._pw_client()
        # Optionale url: erst dorthin navigieren, dann knipsen. So sind nav+shot ein
        # Aufruf und es kann nicht passieren, dass nach vielen Navigationen alle
        # Screenshots dieselbe (zuletzt besuchte) Seite zeigen.
        url = (arguments.get("url") or "").strip()
        if url:
            await _pw.navigate(client, url=url,
                               wait_until=arguments.get("wait_until", "networkidle"))
        await _pw.screenshot(client, path=str(target), full_page=bool(arguments.get("full_page", True)))
        if not target.exists():
            return (f"Screenshot fehlgeschlagen: {target} wurde nicht erzeugt.", True)
        return (f"Screenshot gespeichert: {target} ({target.stat().st_size} Bytes)", False)

    async def _dispatch_mcp(self, rest: str, arguments: dict) -> tuple[str, bool]:
        server, _, tool = rest.partition("__")
        if not server or not tool:
            return (f"Ungueltiger MCP-Toolname: mcp__{rest}", True)
        res = await _mcp.call_tool(server, tool, arguments)
        return (res.get("content", ""), bool(res.get("is_error")))
