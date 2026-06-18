# uc-agent-core

The agentic loop, lifted out of the QATAKI app into this workbench's `shelf/`.

An LLM runs against a set of tools (Playwright, MCP servers, skills, artifact
writers) in a loop: call the model, run any requested tools, feed the results
back, repeat until it answers without a tool call — or a limit, budget, or the
emergency-stop intervenes. Runs stream step by step.

It owns no application state. The session object is passed in per call; settings,
the LLM wrapper, the cancellation runner, the killswitch, and the MCP client are
injected by the host, all with safe defaults.

## Wiring

```python
import uc_agent_core as ac

ac.set_settings_loader(my_settings.load)
ac.set_llm(my_llm)                        # key_present(pt), _provider(s), _text(resp)
ac.set_cancellation(my_cancellation)      # await run(coro)
ac.set_killswitch(my_killswitch)          # -> bool
ac.set_mcp_client(my_mcp)                 # load_config / list_tools / call_tool

async for event in ac.loop.astream(session, "check the login form"):
    ...
```

## Needs alongside it

The three sibling shelf blocks: `uc-llm-provider`, `uc-llm-cost`,
`uc-playwright-driver`. The host installs them together.

Part of my QA/TA-with-AI experiments.
