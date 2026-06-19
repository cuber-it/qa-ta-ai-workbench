"""
Agentic Loop — fuehrt einen Auftrag mit Tools aus.

Ablauf: LLM-Call mit Tool-Specs -> bei Tool-Use jeden Aufruf ueber die
Registry ausfuehren -> ToolResult zurueckspielen -> wiederholen, bis das
LLM ohne Tool-Aufruf antwortet (final) oder ein Limit/Stop greift.

Eingebettet: NOTAUS (sofortiger Stop), Cancellation (laufender Call killbar),
cost_guard (Run-Limits akkumulieren ueber die Schritte; Tages-/Monatsbudget),
max_iterations gegen Endlosschleifen. Alles wird ins Session-Protokoll
geschrieben.
"""
from __future__ import annotations

import asyncio
import logging
import time

from uc_llm_provider import ChatRequest
from uc_llm_provider.core.models import ToolChoiceAuto, ToolResultBlock

from uc_llm_cost import cost_guard

from .registry import ToolRegistry
from . import hooks, prompts, skills

log = logging.getLogger(__name__)


def _short(v, n: int = 120) -> str:
    s = v if isinstance(v, str) else repr(v)
    return s if len(s) <= n else s[:n] + "…"

# Injection hooks — the host wires these via uc_agent_core.set_*(). Safe defaults
# keep the module importable standalone; a real run needs llm + settings wired.
_killswitch = lambda: False       # -> bool, True hard-stops
_settings_loader = lambda: {}     # -> settings dict
_llm = None                       # obj: key_present(pt), _provider(s), _text(resp)
_cancellation = None              # obj: await run(coro)
_usage_sink = None                # callable(run_id, model, input_tokens, output_tokens) or None

# Fallback, falls prompts/system.md fehlt.
_FALLBACK_SYSTEM = (
    "Du bist der QATAKI-Testagent. Nutze die verfuegbaren Tools (pw__*, mcp__*, "
    "skill__*) zielgerichtet und pruefe Ergebnisse am tatsaechlichen Inhalt. "
    "Fasse dich knapp. Ist die Aufgabe erfuellt, antworte ohne weiteren Tool-Aufruf."
)


def build_system() -> str:
    """Systemprompt aus prompts/system.md + angehaengtem Skill-Katalog."""
    base = prompts.load_prompt("system") or _FALLBACK_SYSTEM
    cat = skills.catalog_text()
    return f"{base}\n\n{cat}" if cat else base


_MAX_CONSEC_ERRORS = 3


async def astream(session, user_text: str, *, max_iterations: int | None = None,
                  output_validator=None, registry=None):
    """Agent-Lauf als Event-Strom. Yields dicts mit 'type':
    start | assistant | tool_use | tool_result | final | note | error | done.
    output_validator: optional Callable[[str], str|None] — prueft die finale
    Antwort; bei Fehler genau ein Korrektur-Feedback ans LLM. Schreibt parallel
    ins Session-Protokoll."""
    if _killswitch():
        session.log("error", reason="NOTAUS aktiv")
        yield {"type": "error", "message": "NOTAUS aktiv"}
        yield {"type": "done", "stopped": "notaus", "iterations": 0, "final": None, "costs": {}}
        return

    s = _settings_loader()
    run = getattr(session, "run", {}) or {}
    prov_t = (run.get("provider") or "").strip() or s.get("provider_type")
    if prov_t != s.get("provider_type"):
        if not _llm.key_present(prov_t):
            session.log("error", reason=f"Kein API-Key fuer Provider {prov_t}")
            yield {"type": "error", "message": f"Kein API-Key fuer {prov_t}"}
            yield {"type": "done", "stopped": "no-key", "iterations": 0, "final": None, "costs": {}}
            return
        s = {**s, "provider_type": prov_t, "model": ""}
    run_model = (run.get("model") or "").strip()
    if run_model:                       # Run-Modell hat Vorrang vor dem globalen Default
        s = {**s, "model": run_model}
    run_temp = (str(run.get("temperature") or "")).strip()
    if run_temp:                        # Run-Temperatur hat Vorrang vor agent_temperature
        try:
            s = {**s, "agent_temperature": float(run_temp)}
        except ValueError:
            pass
    if max_iterations is None:
        max_iterations = int(s.get("agent_max_iterations", 15))
    prov = _llm._provider(s)
    model = s.get("model") or ""
    if not model:
        try:
            model = prov.get_default_model()
        except Exception:
            model = "default"
    provider = s.get("provider_type") or ""

    system = build_system()
    run_art = str(session.artifact_dir())
    ctx = []
    if run.get("url"):
        ctx.append(f"Basis-URL fuer diese Aufgabe: {run['url']} — nutze sie, wenn die Aufgabe keine andere URL nennt.")
    if run.get("description"):
        ctx.append(f"Auftrag/Beschreibung des Runs: {run['description']}")
    ctx.append(f"Artefakte (z. B. .feature-Dateien) speicherst du mit artifact__save; Zielordner: {run_art}")
    if ctx:
        system = system + "\n\n" + "\n".join(ctx)
    session.add_user(user_text)
    session.log("system", text=system)
    log.info("Run gestartet (session=%s, model=%s, max_iter=%d)", session.id, model, max_iterations)
    yield {"type": "start", "session_id": session.id}

    # Browser/Registry kann vom Aufrufer geliehen werden (session-scoped, ueber
    # mehrere Nachrichten hinweg). Nur selbst erzeugte Registry wird geschlossen.
    owns_registry = registry is None
    reg = registry or ToolRegistry(headless=bool(run.get("headless", True)), artifacts_path=run_art)
    guard = cost_guard.CostGuard()
    run_costs = cost_guard.RunCosts()
    final = None
    stopped = None
    it = 0
    consec_errors = 0
    validated_once = False
    try:
        while it < max_iterations:
            it += 1
            log.debug("Iteration %d/%d (model=%s)", it, max_iterations, model)
            if _killswitch():
                stopped = "notaus"; session.log("error", reason="NOTAUS aktiv")
                yield {"type": "error", "message": "NOTAUS aktiv"}; break
            try:
                guard.check_budget()
            except cost_guard.CostLimitExceeded as e:
                stopped = "budget"; session.log("error", reason=str(e.reason))
                yield {"type": "error", "message": f"Budget: {e.reason}"}; break

            req = ChatRequest(
                model=model,
                messages=session.to_messages(),
                system=system,
                max_tokens=int(s.get("agent_max_tokens", s.get("max_tokens", 1024))),
                temperature=float(s.get("agent_temperature", s.get("temperature", 0.7))),
                tools=await reg.tool_specs(),
                tool_choice=ToolChoiceAuto(),
            )
            log.debug("LLM-Call -> model=%s msgs=%d tools=%d max_tokens=%d temp=%.2f",
                      model, len(req.messages), len(req.tools or []),
                      req.max_tokens, req.temperature)
            _t0 = time.monotonic()
            try:
                resp = await _cancellation.run(prov.chat(req))
            except asyncio.CancelledError:
                stopped = "abgebrochen"; session.log("error", reason="durch NOTAUS abgebrochen")
                log.warning("LLM-Call abgebrochen (NOTAUS) nach %.0fms", (time.monotonic() - _t0) * 1000)
                yield {"type": "error", "message": "abgebrochen"}; break
            except Exception as e:  # noqa: BLE001
                log.error("LLM-Call fehlgeschlagen nach %.0fms: %s: %s",
                          (time.monotonic() - _t0) * 1000, type(e).__name__, e, exc_info=True)
                raise

            u = resp.usage
            log.info("LLM-Antwort: in=%d out=%d stop=%s tool_uses=%d %.0fms",
                     getattr(u, "input_tokens", 0), getattr(u, "output_tokens", 0),
                     getattr(resp, "stop_reason", "?"), len(resp.tool_uses or []),
                     (time.monotonic() - _t0) * 1000)
            if _usage_sink is not None:
                try:
                    _usage_sink(session.id, provider, model,
                                getattr(u, "input_tokens", 0), getattr(u, "output_tokens", 0))
                except Exception:  # noqa: BLE001 — Logging darf den Lauf nie stoppen
                    log.debug("usage_sink-Fehler", exc_info=True)
            try:
                warns = guard.record_llm_call(run_costs,
                    getattr(u, "input_tokens", 0), getattr(u, "output_tokens", 0), model=model)
            except cost_guard.CostLimitExceeded as e:
                session.add_assistant(resp.content)
                stopped = "run-limit"; session.log("error", reason=str(e.reason))
                yield {"type": "error", "message": f"Run-Limit: {e.reason}"}; break
            for w in (warns or []):
                session.log("note", reason="budget", detail=w.reason)
                yield {"type": "note", "message": f"⚠ {w.reason}"}

            session.add_assistant(resp.content)
            text = _llm._text(resp)
            if text:
                yield {"type": "assistant", "text": text}

            tool_uses = resp.tool_uses
            if tool_uses:
                results = []
                for tu in tool_uses:
                    log.info("Tool %s(%s)", tu.name, _short(tu.input))
                    yield {"type": "tool_use", "id": tu.id, "name": tu.name, "input": tu.input}
                    blocked = hooks.check_tool(tu.name, tu.input)
                    if blocked:
                        content, is_error = blocked, True
                        log.warning("Tool %s -> blockiert: %s", tu.name, _short(content))
                    else:
                        content, is_error = await reg.dispatch(tu.name, tu.input)
                    results.append(ToolResultBlock(tool_use_id=tu.id, content=content, is_error=is_error))
                    yield {"type": "tool_result", "tool_use_id": tu.id,
                           "content": content, "is_error": is_error}
                session.add_tool_results(results)
                consec_errors = consec_errors + 1 if (results and all(r.is_error for r in results)) else 0
                if consec_errors >= _MAX_CONSEC_ERRORS:
                    stopped = "tool-errors"
                    log.error("Run gestoppt: %d fehlerhafte Tool-Runden in Folge", consec_errors)
                    session.log("error", reason=f"{consec_errors} fehlerhafte Tool-Runden in Folge")
                    yield {"type": "error", "message": "zu viele Tool-Fehler in Folge"}; break
                continue

            final = text
            if output_validator and not validated_once:
                verr = output_validator(final or "")
                if verr:
                    validated_once = True
                    session.log("note", reason="output-validation", detail=verr)
                    yield {"type": "note", "message": f"Validierung: {verr}"}
                    session.add_user(
                        f"Die Antwort erfuellt die Vorgabe nicht: {verr} "
                        "Bitte korrigiere sie und gib nur das korrigierte Ergebnis aus.")
                    continue
            log.info("Run fertig nach %d Iteration(en)", it)
            session.log("final", text=final or "")
            yield {"type": "final", "text": final or ""}
            break
        else:
            stopped = "max-iterations"
            log.warning("Run gestoppt: max_iterations (%d) erreicht", max_iterations)
            session.log("error", reason=f"max_iterations ({max_iterations}) erreicht")
            yield {"type": "error", "message": f"max_iterations ({max_iterations}) erreicht"}
    finally:
        if owns_registry:
            await reg.aclose()

    log.info("Run beendet: stopped=%s, iterationen=%d", stopped, it)
    yield {"type": "done", "stopped": stopped, "iterations": it,
           "final": final, "costs": run_costs.to_dict()}


async def run(session, user_text: str, *, max_iterations: int | None = None,
              output_validator=None, registry=None) -> dict:
    """Nicht-streamender Lauf: konsumiert astream und gibt das Endergebnis."""
    final = None; stopped = None; it = 0; costs = {}
    async for ev in astream(session, user_text, max_iterations=max_iterations,
                            output_validator=output_validator, registry=registry):
        if ev["type"] == "done":
            stopped = ev["stopped"]; it = ev["iterations"]
            final = ev.get("final"); costs = ev["costs"]
    return {"session_id": session.id, "final": final, "stopped": stopped,
            "iterations": it, "costs": costs}
