"""Deterministic tests for uc-agent-core.

No real LLM / browser / MCP, no model behaviour — the host's pieces (session,
llm, cancellation, killswitch, mcp) are faked and injected via the public setters.
Only the loop's control flow, registry, skills, prompts, hooks and validators are
exercised.
"""
import asyncio

import pytest

import uc_agent_core as ac
from uc_agent_core import skills, prompts, hooks, validators, loop as L
from uc_agent_core import registry as _registry
from uc_agent_core.registry import ToolRegistry
from uc_llm_cost import cost_guard
from uc_llm_provider.core.models import (
    ChatResponse, Message, Usage, FinishReason, TextBlock, ToolUseBlock,
)


# ── Fakes (the host's responsibility, here minimal) ──────────────────────────
class FakeSession:
    def __init__(self, tmp):
        self.id = "test-sess"
        self.run = {}
        self._tmp = tmp

    def add_user(self, text): pass
    def add_assistant(self, content): pass
    def add_tool_results(self, results): pass
    def to_messages(self): return [Message(role="user", content="x")]
    def log(self, *a, **k): pass
    def artifact_dir(self): return self._tmp


def _resp(blocks, stop):
    return ChatResponse(model="stub", content=blocks, stop_reason=stop,
                        usage=Usage(input_tokens=5, output_tokens=5))


class _Stub:
    def __init__(self, mode): self.mode = mode
    def get_default_model(self): return "stub"

    async def chat(self, req):
        if self.mode == "bad_tool":
            return _resp([ToolUseBlock(id="t", name="pw__nope", input={})], FinishReason.tool_use)
        if self.mode == "good_tool":
            return _resp([ToolUseBlock(id="t", name="skill__list", input={})], FinishReason.tool_use)
        return _resp([TextBlock(text="fertig")], FinishReason.stop)


class FakeLLM:
    mode = "final"
    def key_present(self, pt): return True
    def _provider(self, s): return _Stub(FakeLLM.mode)
    def _text(self, resp):
        c = resp.content
        if isinstance(c, str):
            return c
        return "".join(getattr(b, "text", "") or "" for b in (c or []))


class FakeCancellation:
    async def run(self, coro): return await coro


@pytest.fixture(autouse=True)
def wire(tmp_path, monkeypatch):
    ac.set_settings_loader(lambda: {"provider_type": "openai", "model": "stub",
                                    "agent_max_iterations": 15, "agent_max_tokens": 256,
                                    "agent_temperature": 0.0})
    ac.set_llm(FakeLLM())
    ac.set_cancellation(FakeCancellation())
    ac.set_killswitch(lambda: False)
    ac.set_mcp_client(_registry._NullMcp())
    monkeypatch.setattr(cost_guard.CostGuard, "record_llm_call", lambda self, *a, **k: None)
    monkeypatch.setattr(cost_guard.CostGuard, "check_budget", lambda self: None)
    FakeLLM.mode = "final"
    yield


def _sess(tmp_path):
    return FakeSession(tmp_path)


# ── Skills / Prompts ─────────────────────────────────────────────────────────
def test_skills_catalog_and_load():
    names = {x["name"] for x in skills.list_skills()}
    assert {"explore-webapp", "write-feature", "plan-task"} <= names
    assert "Verfuegbare Skills" in skills.catalog_text()
    assert skills.load_skill("write-feature")
    assert skills.load_skill("gibtsnicht") is None


def test_prompt_loads():
    assert prompts.load_prompt("system")           # non-empty
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


def test_validator_gherkin():
    assert validators.gherkin("nur text") is not None
    assert validators.gherkin("Feature: X\n  Szenario: Y\n  Wenn a\n  Dann b") is None


# ── Registry ─────────────────────────────────────────────────────────────────
async def test_registry_specs_and_dispatch():
    reg = ToolRegistry()
    names = [s.name for s in await reg.tool_specs()]
    assert "skill__list" in names and "skill__load" in names
    assert sum(n.startswith("pw__") for n in names) == 14
    assert "pw__screenshot" in names
    assert not any(n.startswith("mcp__") for n in names)   # NullMcp -> keine mcp-Tools
    out, err = await reg.dispatch("skill__load", {"name": "write-feature"})
    assert err is False and out
    assert (await reg.dispatch("bogus", {}))[1] is True
    await reg.aclose()


# ── Loop: Stop-Zweige / Validator / Guardrail (Stub-Provider) ────────────────
async def test_stop_tool_errors(tmp_path):
    FakeLLM.mode = "bad_tool"
    res = await L.run(_sess(tmp_path), "x", max_iterations=5)
    assert res["stopped"] == "tool-errors"


async def test_stop_max_iterations(tmp_path):
    FakeLLM.mode = "good_tool"
    res = await L.run(_sess(tmp_path), "x", max_iterations=3)
    assert res["stopped"] == "max-iterations"
    assert res["iterations"] == 3


async def test_stop_budget(tmp_path, monkeypatch):
    def boom(self): raise cost_guard.CostLimitExceeded("Budget")
    monkeypatch.setattr(cost_guard.CostGuard, "check_budget", boom)
    res = await L.run(_sess(tmp_path), "x", max_iterations=3)
    assert res["stopped"] == "budget"


async def test_stop_cancel(tmp_path):
    class Cancel:
        async def run(self, coro):
            coro.close()
            raise asyncio.CancelledError()
    ac.set_cancellation(Cancel())
    res = await L.run(_sess(tmp_path), "x", max_iterations=3)
    assert res["stopped"] == "abgebrochen"


async def test_stop_notaus_early(tmp_path):
    ac.set_killswitch(lambda: True)
    res = await L.run(_sess(tmp_path), "x", max_iterations=3)
    assert res["stopped"] == "notaus"
    assert res["iterations"] == 0


async def test_output_validator_retry(tmp_path):
    calls = {"n": 0}
    def v(text):
        calls["n"] += 1
        return "fehlt" if calls["n"] == 1 else None
    res = await L.run(_sess(tmp_path), "x", max_iterations=4, output_validator=v)
    assert calls["n"] == 1
    assert res["stopped"] is None
    assert res["iterations"] == 2


async def test_loop_guardrail_blocks(tmp_path):
    FakeLLM.mode = "good_tool"
    hooks.tool_guards.append(hooks.deny_tools("skill__list"))
    try:
        res = await L.run(_sess(tmp_path), "x", max_iterations=5)
        assert res["stopped"] == "tool-errors"
    finally:
        hooks.tool_guards.clear()
