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
import logging
import time
from pathlib import Path

from uc_llm_provider.core.models import ToolDefinition

log = logging.getLogger(__name__)


def _short(v, n: int = 160) -> str:
    s = v if isinstance(v, str) else repr(v)
    return s if len(s) <= n else s[:n] + "…"

from uc_playwright_driver import tools as _pw
import uc_credentials as _creds
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

# Standard-Keyword-Satz: jeder Eintrag gibt einem Treiber-Kommando einen
# knappen, durchgaengigen Keyword-Namen (snake_case). Agent und Mensch nutzen
# diese Namen; das Tool heisst pw__<keyword>. Links = Keyword, rechts = Name der
# uc_playwright_driver-Funktion. 'screenshot' fehlt bewusst — sie laeuft als
# artefakt-bewusster Sonderfall unter dem Keyword 'shot' (s. _dispatch_screenshot).
_KEYWORDS: dict[str, str] = {
    # Navigation
    "open": "navigate", "url": "current_url", "back": "go_back",
    "forward": "go_forward", "reload": "reload",
    # Lesen / Inhalt
    "title": "get_title", "text": "get_text", "texts": "get_all_texts",
    "page_text": "get_page_content", "html": "get_html", "links": "get_links",
    "attr": "get_attribute", "aria": "get_aria_snapshot",
    "console": "get_console_messages", "requests": "get_page_requests",
    # Finden / Beschreiben
    "find_role": "find_by_role", "find_text": "find_by_text",
    "find_label": "find_by_label", "find_placeholder": "find_by_placeholder",
    "find_testid": "find_by_test_id", "find_interactive": "find_interactive_elements",
    "describe": "describe_element",
    # Klicken
    "click": "click", "click_text": "click_by_text", "click_role": "click_by_role",
    "double_click": "double_click", "right_click": "right_click",
    # Eingabe / Formular
    "fill": "fill", "fill_label": "fill_by_label", "type": "type_text",
    "clear": "clear", "press": "press", "check": "check", "uncheck": "uncheck",
    "select": "select_option", "select_text": "select_option_by_text",
    "hover": "hover", "focus": "focus", "upload": "upload_file", "drag": "drag_and_drop",
    # Dialoge
    "accept_dialog": "accept_dialog", "dismiss_dialog": "dismiss_dialog",
    # Warten
    "wait": "wait_for", "wait_hidden": "wait_for_hidden", "wait_url": "wait_for_url",
    "wait_response": "wait_for_response", "wait_download": "wait_for_download",
    # Pruefen (web-first Assertions)
    "visible": "expect_visible", "hidden": "expect_hidden", "has_text": "expect_text",
    "has_value": "expect_value", "count_is": "expect_count", "url_is": "expect_url",
    "title_is": "expect_title",
    # Tabs
    "tab_new": "new_tab", "tab_list": "list_tabs", "tab_switch": "switch_tab",
    "tab_close": "close_tab",
    # Frames
    "frame": "switch_to_frame", "frame_main": "switch_to_main",
    # Storage / Cookies
    "cookies": "get_cookies", "set_cookie": "set_cookie", "clear_cookies": "clear_cookies",
    "storage": "get_local_storage", "set_storage": "set_local_storage",
    "clear_storage": "clear_storage",
    # Netzwerk
    "mock": "mock_route", "unmock": "clear_route", "abort": "abort_route",
    # Skript
    "js": "execute_script",
    # Ansicht / Aufnahme
    "shot_element": "screenshot_element", "scroll": "scroll_to", "scroll_page": "scroll_page",
    "viewport": "set_viewport", "use_browser": "set_browser", "headless": "set_headless",
    "rec_start": "start_recording", "rec_stop": "stop_recording",
    "rec_actions": "recording_show_actions",
}

# Kuratierte Beschreibungen/Schemas fuer das Kernset (keyed by Keyword). Diese
# ueberschreiben die automatisch aus der Signatur erzeugten Eintraege.
_KW_OVERRIDES: dict[str, dict] = {
    "open": {"fn": _pw.navigate, "desc": "Browser zu einer URL navigieren.",
        "schema": {"type": "object", "properties": {
            "url": {"type": "string"},
            "wait_until": {"type": "string", "enum": ["domcontentloaded", "load", "networkidle"], "default": "load"}},
            "required": ["url"]}},
    "page_text": {"fn": _pw.get_page_content, "desc": "Sichtbaren Textinhalt der Seite holen.",
        "schema": {"type": "object", "properties": {"max_length": {"type": "integer", "default": 10000}}}},
    "text": {"fn": _pw.get_text, "desc": "Text eines Elements per CSS-Selektor.",
        "schema": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}},
    "click_text": {"fn": _pw.click_by_text, "desc": "Element mit sichtbarem Text klicken.",
        "schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    "click_role": {"fn": _pw.click_by_role, "desc": "Element per ARIA-Rolle (optional Name) klicken.",
        "schema": {"type": "object", "properties": {"role": {"type": "string"}, "name": {"type": "string", "default": ""}}, "required": ["role"]}},
    "fill_label": {"fn": _pw.fill_by_label, "desc": "Eingabefeld per Label ausfuellen.",
        "schema": {"type": "object", "properties": {"label": {"type": "string"}, "value": {"type": "string"}}, "required": ["label", "value"]}},
    "fill": {"fn": _pw.fill, "desc": "Eingabefeld per CSS-Selektor ausfuellen.",
        "schema": {"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}}, "required": ["selector", "text"]}},
    "find_role": {"fn": _pw.find_by_role, "desc": "Elemente per ARIA-Rolle finden (optional Name).",
        "schema": {"type": "object", "properties": {"role": {"type": "string"}, "name": {"type": "string", "default": ""}}, "required": ["role"]}},
    "wait": {"fn": _pw.wait_for, "desc": "Auf ein Element (CSS-Selektor) warten.",
        "schema": {"type": "object", "properties": {"selector": {"type": "string"}, "timeout": {"type": "integer", "default": 10000}}, "required": ["selector"]}},
    "press": {"fn": _pw.press, "desc": "Taste druecken (optional in einem Element).",
        "schema": {"type": "object", "properties": {"key": {"type": "string"}, "selector": {"type": "string", "default": ""}}, "required": ["key"]}},
}


def _json_type(annotation: object) -> str:
    """JSON-Schema-Typ aus einer (dank `from __future__ import annotations` als
    String vorliegenden) Python-Annotation ableiten. Fallback: string."""
    ann = str(annotation).lower()
    if "bool" in ann:
        return "boolean"
    if "int" in ann:
        return "integer"
    if "float" in ann:
        return "number"
    return "string"


def _schema_for(fn: object) -> dict:
    """input_schema aus der Signatur einer Treiber-Funktion bauen (client weggelassen)."""
    props: dict[str, dict] = {}
    required: list[str] = []
    for pname, p in inspect.signature(fn).parameters.items():
        if pname == "client" or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        prop: dict = {"type": _json_type(p.annotation)}
        if p.default is inspect.Parameter.empty:
            required.append(pname)
        elif isinstance(p.default, (str, int, float, bool)):
            prop["default"] = p.default
        props[pname] = prop
    schema: dict = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


def _build_pw_tools() -> dict[str, dict]:
    """Den Keyword-Katalog in die Tool-Tabelle aufloesen: pro Keyword die
    Treiber-Funktion + Auto-Schema, danach die kuratierten Overrides darueber."""
    tools: dict[str, dict] = {}
    for kw, fn_name in _KEYWORDS.items():
        fn = getattr(_pw, fn_name)
        doc = inspect.getdoc(fn)
        desc = doc.splitlines()[0].strip() if doc else f"Playwright: {kw}"
        tools[kw] = {"fn": fn, "desc": desc, "schema": _schema_for(fn)}
    tools.update(_KW_OVERRIDES)
    return tools


_PW_TOOLS: dict[str, dict] = _build_pw_tools()


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
        specs.append(ToolDefinition(name="pw__shot",
            description=("Screenshot als PNG im Artefakt-Ordner des Runs speichern. Ohne "
                         "url wird die aktuelle Seite geknipst; mit url wird zuerst dorthin "
                         "navigiert und dann geknipst — fuer mehrere Seiten pro Seite ein "
                         "Aufruf mit url."),
            input_schema={"type": "object", "properties": {
                "filename": {"type": "string", "description": "relativer PNG-Dateiname, z. B. 01-startseite.png"},
                "url": {"type": "string", "description": "optional: vorher hierhin navigieren, dann knipsen"},
                "full_page": {"type": "boolean", "default": True, "description": "ganze Seite statt nur Viewport"}},
                "required": ["filename"]}))
        # Credential-Tools: die KI nennt nur den Profilnamen, nie Werte. Aufloesung
        # passiert im Dispatch (s. _dispatch_auth), die Rueckgabe ist redigiert.
        specs.append(ToolDefinition(name="pw__auth",
            description=("HTTP Basic-Auth fuer die folgenden Navigationen aktivieren, "
                         "anhand eines hinterlegten Credential-Profils (nur Profilname "
                         "angeben — die Zugangsdaten bleiben verborgen)."),
            input_schema={"type": "object", "properties": {
                "profile": {"type": "string", "description": "Name des Credential-Profils, z. B. 'myapp'"}},
                "required": ["profile"]}))
        specs.append(ToolDefinition(name="pw__creds",
            description="Verfuegbare Credential-Profile auflisten (nur Namen, keine Werte).",
            input_schema=_OBJ))
        specs.append(ToolDefinition(name="pw__login",
            description=("Formular-Login mit einem hinterlegten Credential-Profil ausfuehren "
                         "(fuellt Benutzer/Passwort und sendet ab). Nur Profilname angeben — "
                         "Feld-Selektoren und Zugangsdaten kommen aus dem Profil, die Werte "
                         "bleiben verborgen."),
            input_schema={"type": "object", "properties": {
                "profile": {"type": "string", "description": "Name eines Profils mit type: form"}},
                "required": ["profile"]}))
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
        """Gibt (content, is_error) zurueck. Loggt die technische Aktion + Ausgang."""
        arguments = arguments or {}
        t0 = time.monotonic()
        try:
            if name.startswith("skill__"):
                res = await self._dispatch_skill(name, arguments)
            elif name.startswith("artifact__"):
                res = await self._dispatch_artifact(name, arguments)
            elif name.startswith("pw__"):
                res = await self._dispatch_pw(name[4:], arguments)
            elif name.startswith("mcp__"):
                res = await self._dispatch_mcp(name[5:], arguments)
            elif name.startswith("rest__"):
                res = ("REST-Tools sind noch nicht verfuegbar.", True)
            else:
                res = (f"Unbekanntes Tool: {name}", True)
            dt = (time.monotonic() - t0) * 1000
            content, is_error = res
            if is_error:
                log.warning("Tool %s -> Fehler (%.0fms): %s", name, dt, _short(content))
            else:
                log.debug("Tool %s -> ok (%.0fms, %d Zeichen)", name, dt, len(content or ""))
            return res
        except Exception as e:  # noqa: BLE001
            dt = (time.monotonic() - t0) * 1000
            log.error("Tool %s abgebrochen (%.0fms): %s: %s",
                      name, dt, type(e).__name__, e, exc_info=True)
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
        if fn_name == "shot":
            return await self._dispatch_screenshot(arguments)
        if fn_name == "auth":
            return await self._dispatch_auth(arguments)
        if fn_name == "login":
            return await self._dispatch_login(arguments)
        if fn_name == "creds":
            return (json.dumps(_creds.list_profiles(), ensure_ascii=False), False)
        t = _PW_TOOLS.get(fn_name)
        if not t:
            return (f"Unbekanntes Playwright-Tool: pw.{fn_name}", True)
        client = await self._pw_client()
        params = set(inspect.signature(t["fn"]).parameters) - {"client"}
        kwargs = {k: v for k, v in arguments.items() if k in params}
        result = t["fn"](client, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        return (str(result), False)

    async def _dispatch_auth(self, arguments: dict) -> tuple[str, bool]:
        """Profil-Handle im Tool-Layer aufloesen und Basic-Auth setzen. Die Werte
        verlassen diese Methode nie — die Rueckgabe nennt nur den Profilnamen."""
        profile = (arguments.get("profile") or "").strip()
        if not profile:
            return ("profile fehlt.", True)
        try:
            hc = _creds.http_credentials(profile)
        except KeyError:
            return (f"Unbekanntes Credential-Profil: {profile!r}. "
                    f"Verfuegbar: {_creds.list_profiles()}", True)
        client = await self._pw_client()
        await _pw.set_basic_auth(client, hc["username"], hc["password"])
        return (f"Basic-Auth fuer Profil {profile!r} aktiv (Zugangsdaten verborgen)", False)

    async def _dispatch_login(self, arguments: dict) -> tuple[str, bool]:
        """Form-Login: Profil im Tool-Layer aufloesen, Felder + Werte aus dem
        Profil, ausfuehren. Werte verlassen diese Methode nie."""
        profile = (arguments.get("profile") or "").strip()
        if not profile:
            return ("profile fehlt.", True)
        try:
            cred = _creds.get(profile)
        except KeyError:
            return (f"Unbekanntes Credential-Profil: {profile!r}. "
                    f"Verfuegbar: {_creds.list_profiles()}", True)
        missing = [f for f in ("user_field", "pass_field", "submit") if not getattr(cred, f)]
        if missing:
            return (f"Profil {profile!r} fehlen Felder fuer den Form-Login: {missing}", True)
        client = await self._pw_client()
        await _pw.login_form(
            client,
            cred.username or "",
            cred.secret(),
            cred.user_field,
            cred.pass_field,
            cred.submit,
            url=cred.url or "",
        )
        return (f"Form-Login fuer Profil {profile!r} ausgefuehrt (Zugangsdaten verborgen)", False)

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
