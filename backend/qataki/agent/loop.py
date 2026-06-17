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

from uc_llm_provider import ChatRequest
from uc_llm_provider.core.models import ToolChoiceAuto, ToolResultBlock

from qataki import cancellation, killswitch, llm, settings_store
from qataki.cost import cost_guard
from qataki.agent.registry import ToolRegistry
from qataki.agent import hooks, prompts, skills

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
                  output_validator=None):
    """Agent-Lauf als Event-Strom. Yields dicts mit 'type':
    start | assistant | tool_use | tool_result | final | note | error | done.
    output_validator: optional Callable[[str], str|None] — prueft die finale
    Antwort; bei Fehler genau ein Korrektur-Feedback ans LLM. Schreibt parallel
    ins Session-Protokoll."""
    if killswitch.is_active():
        session.log("error", reason="NOTAUS aktiv")
        yield {"type": "error", "message": "NOTAUS aktiv"}
        yield {"type": "done", "stopped": "notaus", "iterations": 0, "final": None, "costs": {}}
        return

    s = settings_store.load()
    run = getattr(session, "run", {}) or {}
    prov_t = (run.get("provider") or "").strip() or s.get("provider_type")
    if prov_t != s.get("provider_type"):
        if not llm.key_present(prov_t):
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
    prov = llm._provider(s)
    model = s.get("model") or ""
    if not model:
        try:
            model = prov.get_default_model()
        except Exception:
            model = "default"

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
    yield {"type": "start", "session_id": session.id}

    reg = ToolRegistry(headless=bool(run.get("headless", True)), artifacts_path=run_art)
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
            if killswitch.is_active():
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
            try:
                resp = await cancellation.run(prov.chat(req))
            except asyncio.CancelledError:
                stopped = "abgebrochen"; session.log("error", reason="durch NOTAUS abgebrochen")
                yield {"type": "error", "message": "abgebrochen"}; break

            u = resp.usage
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
            text = llm._text(resp)
            if text:
                yield {"type": "assistant", "text": text}

            tool_uses = resp.tool_uses
            if tool_uses:
                results = []
                for tu in tool_uses:
                    yield {"type": "tool_use", "id": tu.id, "name": tu.name, "input": tu.input}
                    blocked = hooks.check_tool(tu.name, tu.input)
                    if blocked:
                        content, is_error = blocked, True
                    else:
                        content, is_error = await reg.dispatch(tu.name, tu.input)
                    results.append(ToolResultBlock(tool_use_id=tu.id, content=content, is_error=is_error))
                    yield {"type": "tool_result", "tool_use_id": tu.id,
                           "content": content, "is_error": is_error}
                session.add_tool_results(results)
                consec_errors = consec_errors + 1 if (results and all(r.is_error for r in results)) else 0
                if consec_errors >= _MAX_CONSEC_ERRORS:
                    stopped = "tool-errors"
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
            session.log("final", text=final or "")
            yield {"type": "final", "text": final or ""}
            break
        else:
            stopped = "max-iterations"
            session.log("error", reason=f"max_iterations ({max_iterations}) erreicht")
            yield {"type": "error", "message": f"max_iterations ({max_iterations}) erreicht"}
    finally:
        await reg.aclose()

    yield {"type": "done", "stopped": stopped, "iterations": it,
           "final": final, "costs": run_costs.to_dict()}


async def run(session, user_text: str, *, max_iterations: int | None = None,
              output_validator=None) -> dict:
    """Nicht-streamender Lauf: konsumiert astream und gibt das Endergebnis."""
    final = None; stopped = None; it = 0; costs = {}
    async for ev in astream(session, user_text, max_iterations=max_iterations,
                            output_validator=output_validator):
        if ev["type"] == "done":
            stopped = ev["stopped"]; it = ev["iterations"]
            final = ev.get("final"); costs = ev["costs"]
    return {"session_id": session.id, "final": final, "stopped": stopped,
            "iterations": it, "costs": costs}
