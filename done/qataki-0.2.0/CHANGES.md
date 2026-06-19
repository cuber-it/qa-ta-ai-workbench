# Changelog

## 2026-06-17 — fixes

- Runs carry an optional per-run temperature (new + edit dialogs, empty = use the
  global agent default). The agent loop applies the run's temperature with
  precedence over `agent_temperature`; re-run clones it. Invalid values fall back
  to the global default. Same tooltip as the global temperature field.
- The agent composer now requires an **active run**, not just an active project.
  Previously you could type and send with a project but no run selected, which
  sent an empty session id; the input is now disabled until a run is created or
  opened, with a clear placeholder.

## 2026-06-16 — 0.1.0

First usable, publishable release. The agentic workbench runs end to end and is
manageable and reviewable from the UI.

- Version marker: `__version__` in the package, exposed via `GET /api/version`
  and as the FastAPI app version.
- `requirements.txt` with the tested runtime dependencies, so a fresh clone is
  installable (plus a note to run `playwright install chromium`).
- Re-run: `POST /api/agent/sessions/{sid}/rerun` clones a run's metadata
  (project, url, provider, headless, artifacts base) into a new run and returns
  the original task; the run list gets a "↻" action that opens the new run with
  the task pre-filled (the user sends it — no auto-fire).
- Output grid reordered: Aktivität (top-left), Kontext (top-right), Artefakte
  (bottom-left), Lauf (bottom-right).
- Context pane lists the available (global) skills, served by `GET /api/skills`.
- Projects and runs can be renamed and deleted from the sidebar (✎ / ↻ / ×,
  always visible). A run now has a full edit dialog — name, URL, provider, model
  (provider-aware), description — via `POST /api/agent/sessions/{sid}/edit`, so
  the model can be switched mid-run; the change takes effect on the next message.
- Live activity feedback while a run is in progress: an animated indicator in the
  chat and a pulsing dot on the Aktivität pane, with the status text updating to
  the current tool, so it is visible that the agent is working.
- Outputs are one-click copyable: a copy button on every dialog message and on
  each tool result in the activity log (with a clipboard fallback for http/LAN).
- The active run's model is always shown top-right in the header and updates when
  the model is switched.
- Budget limits are editable in Settings → Kosten (hard/soft tokens per run, USD
  per run, tokens per day), persisted to `data/budget.json` and effective from the
  next run. This UI override layer sits above `config.toml` and the env vars, so
  `POST /api/budget` is the authoritative way to change them at runtime.
- Budget soft/sparmode warnings now surface in the dialog as notes (they were
  computed but silently discarded). Each fires once per run and independently, so
  a run that jumps straight past the sparmode threshold still gets the soft one.
- Run config and LLM settings offer a model picker that follows the chosen
  provider (model list from the pricing table, grouped by provider via
  `GET /api/models`). The run stores its model and re-run clones it; the agent
  loop uses the run's model and falls back to the provider default when none is
  chosen.
- `pw__screenshot(filename, url?)` writes a PNG into the run's artifact folder.
  With `url` it navigates there first and then captures, so navigate and screenshot
  happen in one call — avoiding the failure where a weak model navigates through
  every page first and then takes all screenshots, which captured only the last
  page.
- README rewritten for the release: quickstart, honest 0.1.0 status, roadmap
  (structured `.steps`, Playwright-script ingestion, per-project skills/toolsets).


## 2026-06-16 — Config

- `config.toml` at the repo root holds program defaults: `[llm]` (global LLM
  defaults — provider, model, max_tokens, temperature, agent_*),
  `[project_defaults]` (base_url, description, default_provider, artifacts_base),
  `[run_defaults]` (headless) and `[budget]` (cost-firewall limits). Read fresh on
  each access (tomllib, no dependency), with built-in fallbacks when the file or a
  value is missing.
- Settings now layer as built-in defaults < `config.toml [llm]` <
  `data/settings.json`. The Settings UI writes only deviations, so
  `settings.json` is sparse and config changes propagate to every value the user
  has not overridden. API keys stay in `.env`, never in the config.
- The cost firewall layers the same way: built-in defaults < `config.toml
  [budget]` < `QATAKI_MAX_*` environment variables. config.toml is now the single
  home for all defaults (LLM, projects, runs, budget).
- `GET /api/config` exposes the project/run defaults; the "Neues Projekt" form
  pre-fills from them, and project creation fills any empty field server-side
  from the config.

## 2026-06-16 — Projects and runs

Project and run configuration, with run parameters wired into execution.

- Project creation captures name, base URL, description, artifact path and a
  default provider (stored in `data/projects.json`); a "Neues Projekt" dialog
  replaces the single-field prompt.
- A run is created up front with its own parameters via `POST /api/agent/runs`:
  name (defaults to date and time), URL, provider, headless flag, description and
  artifact folder, stored in the session meta. The endpoint inherits URL,
  provider and artifact folder from the project when not given, so any path (UI
  or API) lands with the project's settings.
- Run parameters take effect: the run provider overrides the global setting for
  that run (with an API-key check that stops the run cleanly when the key is
  missing), the headless flag drives the browser tools, and URL plus description
  are passed to the agent as context, so a task without an explicit URL uses the
  project URL. Artifacts live under `<base>/<project-name>/<run-id>`: the project
  folder is derived from the configured base (`artifacts_base`, default
  `~/.qataki`) plus the project name and created on project creation; each run
  adds its own `<run-id>` subfolder. Saves via `artifact__save`/`artifact__list`
  are confined to that folder (tilde expanded, no absolute paths, no `..`).
- Burger menu reworked to: Projekt laden, Einstellungen, Über QATAKI (with an
  about dialog). "Projekt laden" is a placeholder for importing from other
  sources.
- Top bar shows the active provider, model and the all-time token total next to
  the status lamp, and the active project name next to the brand.

## 2026-06-16 — UI

Frontend reliability and the output area.

- Settings load on page init (not only when the dialog opens), so the saved
  provider/model is shown from the start instead of the default placeholder.
- Status lamp reflects readiness, not just connectivity: green only when
  connected, no emergency stop, and an API key exists for the active provider;
  amber when the key is missing; red when disconnected.
- Output pane split into a 2x2 grid: Aktivität (tool activity), Artefakte and
  Kontext (placeholders), Lauf (status and run costs).
- Activity pane pairs each tool call with its result into one card (name, status,
  input, result) instead of two rows, and cards no longer shrink to fit (which
  had clipped their content); the result label no longer shows the raw call id.
- Artefakte pane lists the active run's files (name, size) as a scrollable,
  run-scoped list; double-click opens a file in a new tab. Backend:
  `GET /api/agent/sessions/{id}/artifacts` lists the run folder,
  `GET /api/agent/sessions/{id}/artifacts/{path}` serves a file (path-traversal
  guarded, correct content types so images and video open inline).
- Activity cards collapse on click (caret in the header); each card's output
  hides while the name and status stay visible. A "alle zu / alle auf" toggle in
  the Aktivität header collapses or expands every card at once, and new cards
  follow the current toggle state.

## 2026-06-16 — Agent

Agentic loop for test authoring, plus project/run binding (documenting edb7418).

Agent core (`backend/qataki/agent/`):
- Tool-driven loop over the LLM provider with step-level streaming (the provider
  streams text only, so events are emitted per step: assistant text, tool use,
  tool result, final). Endpoints `/api/agent/message` and `/api/agent/stream` (SSE).
- Sessions persisted as JSONL under `data/sessions/`, replayable on load so a run
  resumes from its recorded history.
- Tool registry merges sources by prefix: `pw__*` (Playwright browser tools),
  `skill__list`/`skill__load`, `mcp__<server>__*` (from the MCP client config),
  and a `rest__*` placeholder.
- `pw__screenshot` saves a PNG of the current page straight into the run's
  artifact folder (path-safe filename, `.png` enforced, full-page by default), so
  screenshots actually land in the Artefakte list instead of being only claimed.
- Skills are markdown files (`agent/skills/<name>/SKILL.md`) with frontmatter; the
  catalogue is injected into the system prompt for progressive disclosure, full
  instructions loaded on demand. Ships explore-webapp, plan-task, write-feature.
- Prompts are external files (`agent/prompts/`). Guardrail hooks can block tool
  calls; output validators can trigger one correction round; a consecutive
  tool-error cap stops runaway runs.
- Agent-specific settings (max tokens, temperature, max iterations), separate from
  the chat settings.
- Tests in `backend/tests/test_agent.py` cover session round-trip, skills, prompts,
  hooks, validators, registry, and the loop stop conditions.

Project/run binding:
- A project groups runs; a run is a session carrying its `project_id` in the
  session meta. Registry in `data/projects.json`; session storage stays flat, so
  earlier sessions without a project are left untouched.
- Endpoints: `/api/projects` (GET/POST), `/api/projects/{id}/rename`,
  `/api/projects/{id}` (DELETE, cascades to the project's runs);
  `/api/agent/sessions?project_id=` filters runs. A new run requires a valid project.
- Sidebar lists projects and their runs; selecting a run restores the dialog and
  tool activity from the recorded protocol, which solves losing a conversation
  after a reload. The composer is disabled until a project is active.

## 2026-06-16

Cost control reactivated and wired end-to-end.

- Pre-call budget gate in `/api/chat`: blocks before any provider call when the
  daily/monthly budget is exceeded, plus a worst-case single-call estimate so no
  oversized call slips through.
- Cost & pricing UI (Settings "Kosten" tab): budget bars (day/month), usage
  overview by model with estimated USD, pricing source status, confirm/reject
  for proposed price changes, and a manual "refresh prices" action.
- API endpoints: `/api/cost/overview`, `/api/budget`,
  `/api/pricing/{status,pending,apply,reject,refresh}`.
- NOTAUS: aborted calls now record a conservative worst-case estimate
  (`cost_analytics.record_estimate`) so the budget is not understated, since the
  provider logs an aborted call with zero tokens.
- Pricing scraper fetch waits for full page load + hydration. Live source pages
  still need tuning (OpenAI blocks headless; the public Anthropic page shows
  subscription tiers, not the API token table) — the built-in price table
  remains the reliable path, scraping stays best-effort and confirm-gated.

## 2026-06-16 — MCP

Built-in MCP client, dynamic servers, no server-package dependencies.

- `mcp_client.py`: generic client (mcp SDK only), empty by default. Add HTTP/SSE
  MCP servers at runtime, choose a primary, optional bearer-token auth per server.
  Transient connections; tools are discovered and callable.
- API: `/api/mcp/servers` (GET/POST/DELETE), `/api/mcp/primary`,
  `/api/mcp/servers/{name}/{tools,test,call}`.
- Settings "MCP" tab: add servers by URL, set primary, list/test tools, and a
  tool tester (JSON args → result).
