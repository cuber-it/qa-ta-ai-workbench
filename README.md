# qa-ta-ai-workbench

A personal workbench for bringing together agents, QA, and test automation.
Not a product, not a finished thing — a room I tinker in. Today may look very
different from yesterday. The constant: making the everyday of QA and test
automation more modern, effective, and pleasant with the help of AI, under two
hard rules — the human keeps the reins, and the rough edges of AI stay in the
workshop and never leak into the result.

See `CONCEPT.md` for the idea behind it.

## Layout

The workbench is the room, not one of the things in it:

- **`shelf/`** — reusable building blocks, each a standalone, installable package
  with its own `pyproject.toml`. Pulled in by Git URL or local path, no PyPI.
  - `playwright-driver` (`uc_playwright_driver`) — a pure Playwright driver.
  - `llm-provider` (`uc_llm_provider`) — one HTTP-based interface over several
    LLM providers, no vendor SDKs.
  - `llm-cost` (`uc_llm_cost`) — LLM cost guard, pricing, and usage analytics;
    generic via injection, no app coupling.
  - `agent-core` (`uc_agent_core`) — a tool-driven agentic loop with cost limits,
    cancellation, and step streaming; host dependencies injected, no app coupling.
- **`done/`** — finished pieces that run and are left alone.
  - `qataki-0.1.0` — the first finished solution: a small agentic QA workbench
    (FastAPI + Alpine.js) built on the four shelf blocks above.
- **`bench/`** — active work in progress (may be unfinished). *Empty for now.*

A building block moves onto the shelf only once a second piece actually reaches
for it — not on spec.

## Running a piece

Each piece under `done/` is self-contained. For example:

```
cd done/qataki-0.1.0
python -m venv .venv && .venv/bin/pip install -r requirements.txt
./qataki-server.sh        # starts on :12288
```
