# Concept

QATAKI exists to answer one question, and to keep answering it as the answer
changes: where can an AI agent genuinely help with the everyday work of QA and
test automation, and where does it have to stay out of the way?

The honest version of that question has two halves, and the second half matters
more than the first.

## Two hard rules

**The human keeps the reins.** The agent proposes, explores, drafts, and
maintains. It does not decide on its own what ships, and it never runs unattended
in a way that matters. There is always a person who can stop it — a killswitch is
a first-class part of the system, not an afterthought — and cost is on a leash by
construction: per-run, per-day and per-month limits that refuse the call rather
than apologise after it.

**The rough edges of AI stay in the workshop.** This is the load-bearing idea.
The model helps *author* and *maintain* tests. The test that comes out the other
end is meant to be plain, deterministic, and able to stand on its own — no model
in the loop at run time, nothing that "self-heals", nothing that behaves
differently on a Tuesday. If a test passes, it passed for a reason you can read.
CI never phones a model.

## The bet

Most of the cost of test automation is not writing the first test. It is the
second year: keeping hundreds of tests honest while the application underneath
them keeps moving. That maintenance is exactly the tedious, pattern-heavy work an
agent is good at — *if* you let it work on readable artifacts instead of a tangle
of brittle code.

So QATAKI treats the **readable artifact** as the durable thing. The agent
explores an application with browser tools, and what it produces is a plain,
tool-agnostic description of behaviour (Gherkin-style `.feature` today) that a
human can read and a generator can turn into runnable code — and, the other
direction, lift existing scripts back into the same shape. The model is the
author and the editor. The artifact is the product. The runner is a detail you
can swap.

## What it's made of

QATAKI is not a framework you adopt. It is a small set of independent building
blocks (the `shelf/`) wired together into a thin app, each usable on its own in a
plain script without the rest:

- a pure Playwright **driver** for the hands;
- one HTTP **LLM interface** over several providers, with no vendor SDKs, so the
  brain is replaceable;
- a **cost guard** that sits in front of every call;
- a **credential store** the agent refers to by handle and never sees the values
  of;
- an **agentic loop** that calls tools natively, streams its steps, can be
  cancelled, and keeps host concerns injected rather than baked in.

On top sits the workbench itself: projects and runs, a dashboard of tiles you
arrange yourself, live logs and cost, capabilities attached over MCP, and — when
you want to watch — a live view of the agent's browser.

## Compared with the heavyweights

The point is not that the established tools are wrong. They are mostly very good
at what they set out to do. QATAKI makes a different, narrower bet, and it helps
to say so plainly.

**Robot Framework** is the closest in spirit: keyword-driven, tabular, genuinely
readable, with a deep library ecosystem and years of production use. If you want
a mature framework to *adopt*, it is a better answer than this will ever be. The
difference is where the work comes from and where it goes. Robot is the
destination you write toward, by hand or with generators bolted on the side;
QATAKI is the workshop, with the AI doing the authoring and the upkeep, and it
stays deliberately agnostic about the destination — Robot could be one of them.
QATAKI shares Robot's taste for readable, keyword/step-layered tests; it just
doesn't want to *be* the runtime.

**Cucumber and BDD** put business-readable `.feature` files in front of
step-definition code. QATAKI keeps the readable feature file but treats it as the
artifact of record rather than a thin veneer over one specific stack, and lets the
agent — not a human typing glue — keep features and steps in sync.

**Selenium, Cypress, Playwright** are the muscle: engines and runners you still
drive by hand. QATAKI uses Playwright as one of its blocks. These are not rivals
so much as the layer the output can target. Their bet is a great engine plus a
good runner; ours is that the tedious authoring and upkeep on top of that engine
is where an agent earns its keep.

**The codeless / AI platforms** — record-and-playback suites, "self-healing"
locators, commercial low-code tools — make the opposite trade on purpose. They
push AI and heuristics *into the running test*: locators that heal themselves,
models that adapt at execution, usually inside a platform you license and live in.
That buys real convenience. It also means your green is partly a model's opinion,
your tests are harder to read and to diff, and you do not fully own the result.
QATAKI puts the AI on the other side of the line: it helps you build the test,
then gets out, so what runs in CI is plain, ownable, and the same every time. The
price is honest — you give up the self-healing safety net in exchange for tests
you can trust without a model in the room.

## What it is not

Not a product, not a stable API, not a roadmap I owe anyone. It is a personal lab
on a homelab, and it changes its mind. Some of what is described here is built and
some is a direction I'm poking at; the branch in front of you may already have
wandered off. Take what's useful, ignore the rest.

The one thing that does not move is the line: the AI helps in the workshop, the
human keeps the reins, and whatever ships is plain, deterministic, and stands on
its own.
