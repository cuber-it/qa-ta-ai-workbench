"""
Deterministische Tests fuer das Agent-Modul.

Bewusst NICHT hier: echte LLM-Laeufe, echter Browser/MCP, Modellverhalten
(z.B. ob der Agent plan-task zieht) — das gehoert in einen Eval, nicht in
Unit-Tests. Sessions laufen in tmp_path, externe Abhaengigkeiten sind
gestubbt; nichts schreibt in echte data/-Dateien.
"""
import asyncio

import pytest

from qataki import cancellation, llm, mcp_client
from uc_llm_cost import cost_guard
from qataki.agent import session as S
from uc_agent_core import skills, prompts, hooks, validators, loop as L
from uc_agent_core.registry import ToolRegistry
from uc_llm_provider.core.models import (
    ChatResponse, Usage, FinishReason, TextBlock, ToolUseBlock, ToolResultBlock,
)


@pytest.fixture
def sess_dir(tmp_path, monkeypatch):
    """Session-Verzeichnis in tmp_path umlenken (keine echten Daten anfassen)."""
    monkeypatch.setattr(S, "_SESS_DIR", tmp_path / "sessions")
    return tmp_path / "sessions"


# ── Session ──────────────────────────────────────────────────────────────────
def test_session_roundtrip(sess_dir):
    s = S.Session.create(title="t")
    s.add_user("hi")
    s.add_assistant([TextBlock(text="ok"), ToolUseBlock(id="1", name="pw__get_title", input={})])
    s.add_tool_results([ToolResultBlock(tool_use_id="1", content="Title", is_error=False)])
    s.add_assistant([TextBlock(text="done")])
    s.log("final", text="done")

    r = S.Session.load(s.id)
    assert [m.role for m in r.messages] == ["user", "assistant", "user", "assistant"]
    tr = r.messages[2].content
    assert isinstance(tr, list) and getattr(tr[0], "type", None) == "tool_result"

    assert s.id in [x["id"] for x in S.list_sessions()]
    proto = S.read_protocol(s.id)
    assert any(e["type"] == "tool_use" for e in proto)
    assert S.delete_session(s.id) is True
    with pytest.raises(KeyError):
        S.read_protocol(s.id)


# ── Skills / Prompts ─────────────────────────────────────────────────────────
def test_skills_catalog_and_load():
    names = {x["name"] for x in skills.list_skills()}
    assert {"explore-webapp", "write-feature", "plan-task"} <= names
    assert "Verfuegbare Skills" in skills.catalog_text()
    body = skills.load_skill("write-feature")
    assert body and "Gherkin" in body
    assert skills.load_skill("explore-webapp")
    assert skills.load_skill("gibtsnicht") is None


def test_prompt_loads():
    assert "QATAKI" in prompts.load_prompt("system")
    assert prompts.load_prompt("gibtsnicht") == ""


# ── Hooks / Validators ───────────────────────────────────────────────────────
def test_hooks_deny_and_check():
    g = hooks.deny_tools("pw__navigate")
    assert g("pw__navigate", {}) is not None
    assert g("pw__get_title", {}) is None

    hooks.tool_guards.clear()
    hooks.tool_guards.append(g)
    try:
        assert hooks.check_tool("pw__navigate", {}) is not None
        assert hooks.check_tool("skill__list", {}) is None
    finally:
        hooks.tool_guards.clear()

    def boom(name, args):
        raise RuntimeError("x")

    hooks.tool_guards.append(boom)
    try:
        assert "Guard-Fehler" in (hooks.check_tool("any", {}) or "")
    finally:
        hooks.tool_guards.clear()


def test_validator_gherkin():
    assert validators.gherkin("nur text") is not None
    assert validators.gherkin("Feature: X\n  Szenario: Y\n  Wenn a\n  Dann b") is None
    assert validators.gherkin("Feature: X\n  Given a") is not None  # kein Scenario


# ── Registry ─────────────────────────────────────────────────────────────────
async def test_registry_specs_and_dispatch(monkeypatch):
    monkeypatch.setattr(mcp_client, "load_config", lambda: {"servers": {}, "primary": None})
    reg = ToolRegistry()
    names = [s.name for s in await reg.tool_specs()]
    assert "skill__list" in names and "skill__load" in names
    assert sum(n.startswith("pw__") for n in names) == 14
    assert "pw__screenshot" in names
    assert not any(n.startswith("mcp__") for n in names)

    out, err = await reg.dispatch("skill__load", {"name": "write-feature"})
    assert err is False and "Gherkin" in out
    assert (await reg.dispatch("skill__load", {"name": "nope"}))[1] is True
    assert (await reg.dispatch("rest__foo", {}))[1] is True
    assert (await reg.dispatch("bogus", {}))[1] is True
    assert (await reg.dispatch("pw__does_not_exist", {}))[1] is True  # kein Browser
    await reg.aclose()


# ── Loop: Stop-Zweige / Validator / Guardrail (Stub-Provider) ────────────────
def _resp(blocks, stop):
    return ChatResponse(model="stub", content=blocks, stop_reason=stop,
                        usage=Usage(input_tokens=5, output_tokens=5))


class _Stub:
    def __init__(self, mode):
        self.mode = mode

    def get_default_model(self):
        return "stub"

    async def chat(self, req):
        if self.mode == "bad_tool":
            return _resp([ToolUseBlock(id="t", name="pw__nope", input={})], FinishReason.tool_use)
        if self.mode == "good_tool":
            return _resp([ToolUseBlock(id="t", name="skill__list", input={})], FinishReason.tool_use)
        return _resp([TextBlock(text="fertig")], FinishReason.stop)


def _patch_base(mp, mode):
    """Externe Abhaengigkeiten der Loop deterministisch neutralisieren."""
    mp.setattr(mcp_client, "load_config", lambda: {"servers": {}, "primary": None})
    mp.setattr(llm, "_provider", lambda s, m=mode: _Stub(m))
    mp.setattr(L, "_killswitch", lambda: False)
    mp.setattr(cost_guard.CostGuard, "record_llm_call", lambda self, *a, **k: None)
    mp.setattr(cost_guard.CostGuard, "check_budget", lambda self: None)


async def test_stop_tool_errors(sess_dir, monkeypatch):
    _patch_base(monkeypatch, "bad_tool")
    res = await L.run(S.Session.create(), "x", max_iterations=5)
    assert res["stopped"] == "tool-errors"


async def test_stop_max_iterations(sess_dir, monkeypatch):
    _patch_base(monkeypatch, "good_tool")
    res = await L.run(S.Session.create(), "x", max_iterations=3)
    assert res["stopped"] == "max-iterations"
    assert res["iterations"] == 3


async def test_stop_budget(sess_dir, monkeypatch):
    _patch_base(monkeypatch, "final")

    def boom(self):
        raise cost_guard.CostLimitExceeded("Budget")

    monkeypatch.setattr(cost_guard.CostGuard, "check_budget", boom)
    res = await L.run(S.Session.create(), "x", max_iterations=3)
    assert res["stopped"] == "budget"


async def test_stop_cancel(sess_dir, monkeypatch):
    _patch_base(monkeypatch, "final")

    async def crun(coro):
        coro.close()
        raise asyncio.CancelledError()

    monkeypatch.setattr(cancellation, "run", crun)
    res = await L.run(S.Session.create(), "x", max_iterations=3)
    assert res["stopped"] == "abgebrochen"


async def test_stop_notaus_early(sess_dir, monkeypatch):
    _patch_base(monkeypatch, "final")
    monkeypatch.setattr(L, "_killswitch", lambda: True)
    res = await L.run(S.Session.create(), "x", max_iterations=3)
    assert res["stopped"] == "notaus"
    assert res["iterations"] == 0


async def test_output_validator_retry(sess_dir, monkeypatch):
    _patch_base(monkeypatch, "final")
    calls = {"n": 0}

    def v(text):
        calls["n"] += 1
        return "fehlt" if calls["n"] == 1 else None

    res = await L.run(S.Session.create(), "x", max_iterations=4, output_validator=v)
    assert calls["n"] == 1            # einmal validiert, dann akzeptiert
    assert res["stopped"] is None
    assert res["iterations"] == 2     # erster final + korrigierter final


async def test_loop_guardrail_blocks(sess_dir, monkeypatch):
    _patch_base(monkeypatch, "good_tool")
    hooks.tool_guards.append(hooks.deny_tools("skill__list"))
    try:
        res = await L.run(S.Session.create(), "x", max_iterations=5)
        assert res["stopped"] == "tool-errors"
    finally:
        hooks.tool_guards.clear()
