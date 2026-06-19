"""QATAKI Rahmen - FastAPI-App: serviert die Oberflaeche + LLM-Anbindung."""
import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from . import applog, cancellation, config, killswitch, llm, mcp_client, projects, settings_store, usagelog
from uc_llm_cost import cost_analytics, cost_guard, pricing, pricing_store
from .cost.pricing_agent import PricingSubagent
from uc_agent_core import loop as agent_loop, skills as agent_skills
from .agent import session as agent_session
from .agent import registries as agent_registries

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "frontend"

app = FastAPI(title="QATAKI", version=__version__)

applog.setup()
applog.set_level(settings_store.load().get("log_level", "INFO"))
usagelog.set_enabled(bool(settings_store.load().get("token_log", True)))
log = applog.get_logger("qataki.api")
applog.get_logger("qataki.main").info("QATAKI %s gestartet", __version__)


@app.on_event("startup")
async def _on_startup():
    agent_registries.start_sweeper()


@app.on_event("shutdown")
async def _on_shutdown():
    await agent_registries.stop_sweeper()
    await agent_registries.close_all()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/version")
def version():
    return {"name": "QATAKI", "version": __version__}


@app.get("/api/skills")
def skills_list():
    """Verfuegbare (globale) Skills: Name + Einsatzzweck."""
    return {"skills": agent_skills.list_skills()}


def _provider_of(model: str) -> str:
    m = model.lower()
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith(("gpt", "chatgpt", "o1", "o3", "o4")):
        return "openai"
    if m.startswith("gemini"):
        return "google"
    if m.startswith(("llama", "mistral", "mixtral", "phi", "qwen")):
        return "ollama"
    return ""


@app.get("/api/models")
def models_by_provider():
    """Bekannte Modelle (aus der Preisliste), nach Provider gruppiert."""
    out: dict[str, list[str]] = {}
    for model in pricing.list_models():
        prov = _provider_of(model)
        if prov:
            out.setdefault(prov, []).append(model)
    for prov in out:
        out[prov].sort()
    return {"models": out}


# ── Settings ────────────────────────────────────────────────────────────────
@app.get("/api/settings")
def get_settings():
    s = settings_store.load()
    return {
        **s,
        "providers": ["anthropic", "openai"],
        "key_present": {p: llm.key_present(p) for p in ("anthropic", "openai")},
    }


class SettingsIn(BaseModel):
    provider_type: str
    model: str = ""
    max_tokens: int = 1024
    temperature: float = 0.7
    agent_max_tokens: int = 16384
    agent_temperature: float = 0.3
    agent_max_iterations: int = 15
    token_log: bool | None = None   # None = unveraendert lassen; true/false schaltet live


@app.post("/api/settings")
def post_settings(body: SettingsIn):
    data = body.model_dump()
    res = settings_store.save(data)
    if data.get("log_level"):
        applog.set_level(data["log_level"])
        log.info("Einstellungen gespeichert (log_level=%s)", data["log_level"])
    elif data.get("token_log") is not None:
        usagelog.set_enabled(bool(data["token_log"]))
        log.info("Einstellungen gespeichert (token_log=%s)", bool(data["token_log"]))
    else:
        log.info("Einstellungen gespeichert")
    return res


# ── Chat / Kosten ───────────────────────────────────────────────────────────
class ChatIn(BaseModel):
    messages: list[dict]
    system: str | None = None


def _estimate_tokens(messages: list[dict], system: str | None) -> int:
    """Grobe Token-Schaetzung (~4 Zeichen/Token) fuer das Pre-Call-Budget-Gate."""
    chars = len(system or "")
    for m in messages:
        chars += len(str(m.get("content", "")))
    return max(1, chars // 4)


@app.post("/api/chat")
async def post_chat(body: ChatIn):
    if killswitch.is_active():
        raise HTTPException(status_code=423, detail="NOTAUS aktiv - alle LLM-Calls gesperrt")
    s = settings_store.load()
    if not llm.key_present(s["provider_type"]):
        raise HTTPException(status_code=400, detail=f"Kein API-Key fuer {s['provider_type']} gesetzt")

    guard = cost_guard.CostGuard()
    # Ebene 4: Tages-/Monatsbudget gerissen -> gar nicht erst anrufen.
    try:
        guard.check_budget()
    except cost_guard.CostLimitExceeded as e:
        raise HTTPException(status_code=402, detail=f"Budget gesperrt: {e.reason}")
    # Worst-Case-Schaetzung des Einzel-Calls -> kein Riesen-Call rutscht durch.
    model = s.get("model") or "default"
    est_in = _estimate_tokens(body.messages, body.system)
    max_out = int(s.get("max_tokens", 1024))
    worst = pricing.calculate_cost(model, est_in, max_out)
    if worst > guard.limits.hard_usd_per_run:
        raise HTTPException(status_code=402,
            detail=f"Einzel-Call-Schaetzung ~${worst:.4f} ueber Run-Limit ${guard.limits.hard_usd_per_run:.2f}")

    try:
        result = await llm.chat(s, body.messages, body.system)
    except asyncio.CancelledError:
        # Provider loggt den Abbruch mit 0 Tokens -> Worst-Case nachtragen,
        # damit das Budget die echten Serverkosten nicht untertreibt.
        try:
            cost_analytics.record_estimate(s["provider_type"], model, est_in, max_out)
        except Exception:  # noqa: BLE001
            pass
        raise HTTPException(status_code=503, detail="Durch NOTAUS abgebrochen")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM-Fehler: {e}")
    return {**result, "cost": llm.cost_summary()}


@app.get("/api/cost")
def get_cost():
    return llm.cost_summary()


# ── Kosten / Budget / Pricing ───────────────────────────────────────────────
@app.get("/api/cost/overview")
def cost_overview(period: str = "month"):
    return cost_analytics.overview(period)


@app.get("/api/budget")
def get_budget():
    return cost_guard.CostGuard().budget_status()


class BudgetIn(BaseModel):
    max_tokens_per_run: int | None = None
    soft_tokens_per_run: int | None = None
    sparmode_tokens: int | None = None
    max_usd_per_run: float | None = None
    max_tokens_per_day: int | None = None
    max_usd_per_day: float | None = None
    max_usd_per_month: float | None = None
    confirm_above_usd: float | None = None


@app.post("/api/budget")
def set_budget(body: BudgetIn):
    """Budget-Limits setzen (persistent in data/budget.json, wirkt ab naechstem Run)."""
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    cost_guard.save_overrides(fields)
    return cost_guard.CostGuard().budget_status()


@app.get("/api/pricing/status")
def pricing_status():
    return pricing_store.status()


@app.get("/api/pricing/pending")
def pricing_pending():
    return {"pending": pricing_store.get_pending_diff()}


@app.post("/api/pricing/apply")
def pricing_apply():
    pd = pricing_store.get_pending_diff()
    if not pd:
        raise HTTPException(status_code=404, detail="Kein Pending-Diff vorhanden")
    pricing_store.apply_diff(pd["changes"])
    return {"status": "applied", "count": len(pd["changes"])}


@app.post("/api/pricing/reject")
def pricing_reject():
    pricing_store.reject_pending_diff()
    return {"status": "rejected"}


@app.post("/api/pricing/refresh")
async def pricing_refresh():
    if killswitch.is_active():
        raise HTTPException(status_code=423, detail="NOTAUS aktiv")
    return await PricingSubagent().run()


# ── MCP ─────────────────────────────────────────────────────────────────────
class McpServerIn(BaseModel):
    name: str
    url: str
    transport: str = "http"
    auth_token: str | None = None


class McpPrimaryIn(BaseModel):
    name: str


class McpCallIn(BaseModel):
    tool: str
    arguments: dict = {}


@app.get("/api/mcp/servers")
def mcp_servers():
    return mcp_client.list_servers()


@app.post("/api/mcp/servers")
def mcp_add_server(body: McpServerIn):
    headers = {"Authorization": f"Bearer {body.auth_token}"} if body.auth_token else None
    try:
        res = mcp_client.add_server(body.name, body.url, body.transport, headers)
        log.info("MCP-Server hinzugefügt: %s (%s, %s)", body.name, body.url, body.transport)
        return res
    except ValueError as e:
        log.warning("MCP-Server %s abgelehnt: %s", body.name, e)
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/mcp/servers/{name}")
def mcp_remove_server(name: str):
    log.info("MCP-Server entfernt: %s", name)
    return mcp_client.remove_server(name)


@app.post("/api/mcp/primary")
def mcp_set_primary(body: McpPrimaryIn):
    try:
        res = mcp_client.set_primary(body.name)
        log.info("MCP-Primärserver gesetzt: %s", body.name)
        return res
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Server '{body.name}' nicht gefunden")


@app.get("/api/mcp/servers/{name}/tools")
async def mcp_tools(name: str):
    try:
        return {"tools": await mcp_client.list_tools(name)}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"MCP-Fehler: {e}")


@app.post("/api/mcp/servers/{name}/test")
async def mcp_test(name: str):
    try:
        return await mcp_client.test(name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"MCP-Fehler: {e}")


@app.post("/api/mcp/servers/{name}/call")
async def mcp_call(name: str, body: McpCallIn):
    try:
        return await mcp_client.call_tool(name, body.tool, body.arguments)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"MCP-Fehler: {e}")


# ── NOTAUS / Killswitch ─────────────────────────────────────────────────────
@app.post("/api/emergency-stop")
async def emergency_stop():
    # Flag setzen sperrt jeden weiteren Call sofort (auch ueber Neustart).
    res = killswitch.trigger("manual NOTAUS")
    # Best-Effort: laufende Calls abbrechen (httpx-Verbindung kappen).
    killed = cancellation.kill_all()
    return {**res, "killed_inflight": killed}


@app.post("/api/emergency-resume")
def emergency_resume():
    return killswitch.resume()


@app.get("/api/emergency-status")
def emergency_status():
    return killswitch.status()


# ── Projekte ─────────────────────────────────────────────────────────────────
@app.get("/api/config")
def get_config():
    return {"project_defaults": config.project_defaults(), "run_defaults": config.run_defaults()}


class ProjectIn(BaseModel):
    name: str = ""
    base_url: str = ""
    description: str = ""
    artifacts_path: str = ""
    default_provider: str = ""


@app.get("/api/projects")
def get_projects():
    return {"projects": projects.list_projects()}


def _safe_folder_name(name: str) -> str:
    s = (name or "").strip()
    for ch in '/\\:*?"<>|':
        s = s.replace(ch, "_")
    return s or "Projekt"


@app.post("/api/projects")
def post_project(body: ProjectIn):
    d = config.project_defaults()
    base = (d.get("artifacts_base") or "~/.qataki").rstrip("/")
    folder = body.artifacts_path.strip() or f"{base}/{_safe_folder_name(body.name)}"
    try:
        Path(folder).expanduser().mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    proj = projects.create_project(
        body.name,
        base_url=body.base_url or d["base_url"],
        description=body.description or d["description"],
        artifacts_path=folder,
        default_provider=body.default_provider or d["default_provider"],
    )
    log.info("Projekt angelegt: %s (id=%s)", body.name, proj.get("id", "?"))
    return proj


@app.post("/api/projects/{pid}/rename")
def post_project_rename(pid: str, body: ProjectIn):
    if not projects.rename_project(pid, body.name):
        raise HTTPException(status_code=404, detail="Projekt unbekannt")
    log.info("Projekt umbenannt: %s -> %s", pid, body.name)
    return {"id": pid, "name": body.name}


@app.delete("/api/projects/{pid}")
def delete_project(pid: str):
    if not projects.delete_project(pid):
        raise HTTPException(status_code=404, detail="Projekt unbekannt")
    removed = sum(1 for s in agent_session.list_sessions(pid)
                  if agent_session.delete_session(s["id"]))
    log.info("Projekt gelöscht: %s (%d Runs entfernt)", pid, removed)
    return {"deleted": pid, "runs_removed": removed}


# ── Agent (agentic loop) ────────────────────────────────────────────────────
class AgentMessageIn(BaseModel):
    session_id: str = ""
    text: str
    project_id: str = ""
    max_iterations: int | None = None   # None = aus Agent-Settings


def _agent_session(body: AgentMessageIn):
    """Bestehende Session laden oder neue im (gueltigen) Projekt anlegen."""
    if body.session_id:
        try:
            return agent_session.Session.load(body.session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session unbekannt")
    if not body.project_id or not projects.exists(body.project_id):
        raise HTTPException(status_code=400, detail="Kein gueltiges Projekt fuer den Run")
    return agent_session.Session.create(project_id=body.project_id)


async def _session_registry(sess):
    """Session-scoped Browser/Registry — ueber mehrere Nachrichten wiederverwendet,
    damit die geoeffnete Seite zwischen den Nachrichten eines Runs erhalten bleibt."""
    run = getattr(sess, "run", {}) or {}
    return await agent_registries.get(
        sess.id,
        headless=bool(run.get("headless", True)),
        artifacts_path=str(sess.artifact_dir()),
    )


@app.post("/api/agent/message")
async def agent_message(body: AgentMessageIn):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text fehlt")
    sess = _agent_session(body)
    reg = await _session_registry(sess)
    return await agent_loop.run(sess, body.text, max_iterations=body.max_iterations, registry=reg)


@app.post("/api/agent/stream")
async def agent_stream(body: AgentMessageIn):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text fehlt")
    sess = _agent_session(body)

    async def gen():
        applog.set_run(sess.id)
        reg = await _session_registry(sess)
        try:
            async for ev in agent_loop.astream(sess, body.text,
                                               max_iterations=body.max_iterations,
                                               registry=reg):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        finally:
            applog.clear_run()

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/usage")
def api_usage(limit: int = 500):
    """Token-Verbrauch strukturiert fuer die UI: letzte ``limit`` Eintraege + Summen."""
    return usagelog.read_recent(limit=limit)


@app.get("/api/usage/tokens")
def api_usage_tokens():
    """Token-Verbrauchslog (logs/token-usage.log) als Text-Download.
    Leer, solange noch nichts geloggt wurde."""
    from pathlib import Path
    p = Path(usagelog.path_str())
    if not p.exists():
        return PlainTextResponse("", headers={"X-Token-Log": "empty"})
    return FileResponse(str(p), media_type="text/plain; charset=utf-8",
                        filename="token-usage.log")


@app.get("/api/logs")
def api_logs(pos: int = 0, levels: str = "", run_id: str = "", limit: int = 1000):
    """Inkrementelles App-Log fuers UI. ``levels`` komma-separiert, optional ``run_id``."""
    raw = [x.strip().upper() for x in levels.split(",") if x.strip()]
    norm = ["WARNING" if x == "WARN" else x for x in raw]
    return applog.read_recent(pos=pos, levels=norm or None, run_id=(run_id or None), limit=limit)


@app.get("/api/logs/stream")
async def api_logs_stream(levels: str = "", run_id: str = "", backfill: int = 200):
    """Live-Log via SSE: erst Backfill der letzten Zeilen, dann Push neuer Zeilen."""
    raw = [x.strip().upper() for x in levels.split(",") if x.strip()]
    want = {"WARNING" if x == "WARN" else x for x in raw} or None
    rid = run_id or None

    bc = applog.get_broadcaster()
    if bc is None:
        raise HTTPException(status_code=503, detail="Logging nicht initialisiert")
    bc.bind_loop(asyncio.get_running_loop())
    q = bc.subscribe()

    async def gen():
        try:
            recent = applog.read_recent(
                limit=backfill,
                levels=list(want) if want else None,
                run_id=rid,
            )
            for e in recent["entries"]:
                yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
            while True:
                e = await q.get()
                if want and e["level"] not in want:
                    continue
                if rid and e["run"] != rid:
                    continue
                yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
        finally:
            bc.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class RunIn(BaseModel):
    project_id: str
    name: str = ""
    url: str = ""
    provider: str = ""
    headless: bool = True
    description: str = ""
    artifacts_path: str = ""
    model: str = ""
    temperature: str = ""


@app.post("/api/agent/runs")
def create_run(body: RunIn):
    proj = projects.get_project(body.project_id)
    if not proj:
        raise HTTPException(status_code=400, detail="Kein gültiges Projekt")
    s = agent_session.Session.create(
        title=body.name, project_id=body.project_id,
        url=body.url or proj.get("base_url", ""),
        provider=body.provider or proj.get("default_provider", ""),
        headless=body.headless,
        description=body.description,
        artifacts_path=body.artifacts_path or proj.get("artifacts_path", ""),
        model=body.model,
        temperature=body.temperature,
    )
    log.info("Run angelegt: %s (id=%s, projekt=%s)", s.title, s.id, s.project_id)
    return {"id": s.id, "title": s.title, "project_id": s.project_id, **s.run}


@app.post("/api/agent/sessions/{sid}/rerun")
def rerun_session(sid: str):
    """Klont Meta + erste Aufgabe eines Laufs in einen neuen Lauf (eigene ID)."""
    try:
        events = agent_session.read_protocol(sid)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session unbekannt")
    meta = next((e for e in events if e.get("type") == "session"), None)
    if not meta:
        raise HTTPException(status_code=400, detail="Lauf ohne Metadaten")
    task = next((e.get("text", "") for e in events if e.get("type") == "user"), "")
    old_title = meta.get("title", "") or "Lauf"
    s = agent_session.Session.create(
        title=f"{old_title} (Wiederholung)",
        project_id=meta.get("project_id", ""),
        url=meta.get("url", ""),
        provider=meta.get("provider", ""),
        headless=meta.get("headless", True),
        description=meta.get("description", ""),
        artifacts_path=meta.get("artifacts_path", ""),
        model=meta.get("model", ""),
        temperature=meta.get("temperature", ""),
    )
    log.info("Run wiederholt: %s -> neuer Run %s", sid, s.id)
    return {"id": s.id, "title": s.title, "project_id": s.project_id,
            "task": task, **s.run}


@app.get("/api/agent/sessions")
def agent_sessions(project_id: str | None = None):
    return {"sessions": agent_session.list_sessions(project_id)}


@app.get("/api/agent/sessions/{sid}")
def agent_session_protocol(sid: str):
    try:
        return {"id": sid, "events": agent_session.read_protocol(sid)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Session unbekannt")


@app.get("/api/agent/sessions/{sid}/artifacts")
def agent_artifacts(sid: str):
    try:
        sess = agent_session.Session.load(sid)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session unbekannt")
    d = sess.artifact_dir()
    items = []
    if d.is_dir():
        for p in sorted(d.rglob("*")):
            if p.is_file():
                try:
                    size = p.stat().st_size
                except Exception:
                    size = 0
                items.append({"name": str(p.relative_to(d)), "size": size,
                              "ext": p.suffix.lower().lstrip(".")})
    return {"id": sid, "dir": str(d), "artifacts": items}


@app.get("/api/agent/sessions/{sid}/artifacts/{path:path}")
def agent_artifact_file(sid: str, path: str):
    try:
        sess = agent_session.Session.load(sid)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session unbekannt")
    d = sess.artifact_dir().resolve()
    target = (d / path).resolve()
    try:
        target.relative_to(d)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ungueltiger Pfad")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Artefakt nicht gefunden")
    return FileResponse(str(target))


class SessionRenameIn(BaseModel):
    title: str = ""


@app.post("/api/agent/sessions/{sid}/rename")
def agent_session_rename(sid: str, body: SessionRenameIn):
    if not agent_session.rename_session(sid, body.title):
        raise HTTPException(status_code=404, detail="Session unbekannt")
    log.info("Run umbenannt: %s -> %s", sid, body.title)
    return {"id": sid, "title": body.title}


class SessionEditIn(BaseModel):
    title: str | None = None
    url: str | None = None
    provider: str | None = None
    model: str | None = None
    temperature: str | None = None
    description: str | None = None
    headless: bool | None = None


@app.post("/api/agent/sessions/{sid}/edit")
def agent_session_edit(sid: str, body: SessionEditIn):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not agent_session.update_session(sid, fields):
        raise HTTPException(status_code=404, detail="Session unbekannt")
    log.info("Run bearbeitet: %s (%s)", sid, ", ".join(fields.keys()))
    return {"id": sid, **fields}


@app.delete("/api/agent/sessions/{sid}")
async def agent_session_delete(sid: str):
    if not agent_session.delete_session(sid):
        raise HTTPException(status_code=404, detail="Session unbekannt")
    await agent_registries.close(sid)
    log.info("Run gelöscht: %s", sid)
    return {"deleted": sid}


# ── statische Oberflaeche ───────────────────────────────────────────────────
@app.middleware("http")
async def _no_cache_frontend(request, call_next):
    """Frontend-Assets immer revalidieren -> Browser laeuft nie auf altem Stand."""
    resp = await call_next(request)
    p = request.url.path
    if p == "/" or p.startswith(("/js/", "/css/", "/vendor/")):
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp


app.mount("/css", StaticFiles(directory=FRONTEND / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND / "js"), name="js")
app.mount("/vendor", StaticFiles(directory=FRONTEND / "vendor"), name="vendor")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")
