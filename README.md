# QATAKI

Quality Assurance, Test Automation, AI.

A workbench for designing REST and GUI tests together with an AI agent. You set up a
project, point the agent at a web application, and it explores the app and drafts a
readable, tool-agnostic test description — a Gherkin `.feature` — saved as a run
artifact. Runs, their protocol, and their artifacts are kept per project, so you can
review them, re-run them, and track cost.

See [CONCEPT.md](CONCEPT.md) for the rationale and architecture.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium     # browser for the Playwright tools
cp .env.example .env                                # then add your LLM API key(s)
.venv/bin/python -m uvicorn qataki.main:app --app-dir backend --port 12288 --env-file .env
```

Then open <http://127.0.0.1:12288>.

## Status

**0.1.0 — first usable release.** The agentic workbench runs end to end: create projects
and runs, drive an LLM agent over a web application with Playwright tools, produce
`.feature` artifacts, attach external capabilities via MCP servers, manage settings, and
track cost per run.

## Roadmap

- Structured `.steps` tables alongside the `.feature`, as a first-class authoring flow.
- Ingesting existing Playwright scripts (including codegen output) and lifting them into
  the same format for an AI-assisted re-run.
- Per-project skills and configurable tool-sets, editable from the UI.

## License

See [LICENSE](LICENSE).
