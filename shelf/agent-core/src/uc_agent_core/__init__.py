"""uc-agent-core — a tool-driven agentic loop, generic via injection.

The loop runs an LLM with tools until it answers without a tool call, with
emergency-stop, cancellation, cost limits, and step-level streaming. It carries
no application coupling: the session is passed per call, everything else is
injected by the host with safe defaults.

    import uc_agent_core as ac
    ac.set_settings_loader(settings.load)    # -> settings dict
    ac.set_llm(my_llm)                        # key_present / _provider / _text
    ac.set_cancellation(my_cancellation)      # await run(coro)
    ac.set_killswitch(killswitch.is_active)   # -> bool
    ac.set_mcp_client(my_mcp)                 # load_config / list_tools / call_tool
    result = await ac.loop.run(session, "explore the login page")

Needs its sibling shelf blocks present: uc-llm-provider, uc-llm-cost,
uc-playwright-driver.
"""
from . import loop, registry, hooks, prompts, skills, validators
from .registry import ToolRegistry

__all__ = [
    "loop", "registry", "hooks", "prompts", "skills", "validators", "ToolRegistry",
    "set_settings_loader", "set_llm", "set_cancellation", "set_killswitch", "set_mcp_client",
]


def set_settings_loader(fn):
    """Callable returning the settings dict (provider_type, model, temperature, …)."""
    loop._settings_loader = fn


def set_llm(obj):
    """Object/module providing key_present(pt), _provider(settings), _text(resp)."""
    loop._llm = obj


def set_cancellation(obj):
    """Object/module providing `await run(coro)` for a cancellable LLM call."""
    loop._cancellation = obj


def set_killswitch(fn):
    """Callable returning True when execution must hard-stop. Default: never active."""
    loop._killswitch = fn


def set_mcp_client(obj):
    """Object/module providing load_config(), list_tools(server), call_tool(server, tool, args)."""
    registry._mcp = obj
