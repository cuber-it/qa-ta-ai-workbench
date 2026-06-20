# QATAKI

Quality Assurance, Test Automation, AI.

QATAKI is my personal playground for ideas about how an AI agent, QA, and test
automation fit together. I use it to think through new concepts, rediscover old
ones, and reconstruct established approaches from first principles. Pulling a known
approach apart and building it back up is how I get to the bottom of why it works
and where it breaks.

For that reason it will never be a finished solution. What lives here is whatever
state the current experiment happens to be in, and that state can look quite
different from yesterday's. Some days it grows a feature; some days it changes its
mind about what it wants to be.

One question stays constant underneath all the churn: how can AI make the everyday
work of running QA and building test automation more modern, more effective, and
more pleasant? Two limits stay just as constant. I keep the reins, and the AI never
runs the show. The AI's rough edges stay in the workshop, and they don't get to
leak into the result and ruin the day. The AI helps author and maintain; whatever
test comes out the other end is meant to be plain, deterministic, and able to stand
on its own without a model in the loop.

See [CONCEPT.md](CONCEPT.md) for the current thinking. That changes too.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium     # browser for the Playwright tools
cp .env.example .env                                # then add your LLM API key(s)
.venv/bin/python -m uvicorn qataki.main:app --app-dir backend --port 12288 --env-file .env
```

Then open <http://127.0.0.1:12288>.

## What this is, and what it isn't

- A lab for QA/TA-with-AI ideas, built and run on my own homelab, for myself.
- Not a product, not a stable API, not a roadmap I owe anyone. Expect sharp turns
  and the occasional rewrite.
- Possibly useful to you anyway. Take what helps, ignore the rest.

## Where it is right now

`v0.2.0` is the current snapshot. It is still the agentic workbench from `0.1.0` —
create projects and runs, drive an LLM over a web application with Playwright tools,
produce readable artifacts, attach capabilities over MCP, keep cost on a leash — but
the surface has changed shape. The UI is now a dashboard of floating tiles you
arrange yourself. A project carries a default provider and model that each new run
inherits and can override. A run's settings are editable and persist for that run
alone. And a browser-view tile can mirror what the agent's browser is doing, live,
whenever you want to watch. Underneath, the agent calls its tools natively. As ever,
the branch you are looking at may already have wandered off somewhere else.

For the blow-by-blow, see [CHANGES.md](CHANGES.md).

## Directions I'm poking at (no promises)

- Readable, tool-agnostic test artifacts that export to runnable code and re-import
  cleanly.
- AI as an author and maintainer in the workshop, kept out of the deterministic
  result and out of CI.
- Keyword/step layering, structured step tables, and lifting existing scripts into
  the same format.

## License

See [LICENSE](../../LICENSE) — GNU AGPL-3.0.
