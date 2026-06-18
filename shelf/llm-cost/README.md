# uc-llm-cost

LLM cost control, lifted into this workbench's `shelf/` as a standalone building
block. Three concerns in one small package:

- **cost guard** — per-run / per-day / per-month token and USD limits, soft and
  spar-mode warnings, a hard stop, and editable UI overrides.
- **pricing** — a pricing table plus a persisted, editable pricing store.
- **analytics** — SQLite-backed usage and cost history.

Pure standard library, no dependencies.

## Generic by injection

The package makes no assumption about the host application. It wires three hooks,
all with safe defaults:

```python
import uc_llm_cost

uc_llm_cost.set_data_dir(repo_root)            # data/budget.json, data/pricing.json, logs/*
uc_llm_cost.set_config_loader(load_budget)     # returns the [budget] config dict
uc_llm_cost.set_killswitch(killswitch_active)  # returns True to hard-stop everything
```

Without wiring it still runs: no extra config, killswitch never active, files under
the current working directory.

## Use

```python
from uc_llm_cost import CostGuard, RunCosts

guard = CostGuard()                 # limits layered: defaults < config < env < UI overrides
costs = RunCosts()
warnings = guard.record_llm_call(costs, prompt_tokens=1200, completion_tokens=300, model="gpt-4o-mini")
```

## Install

Lives in the `shelf/` of the qa-ta-ai-workbench monorepo. Pull from Git, no PyPI:

```
pip install "uc-llm-cost @ git+https://github.com/cuber-it/qa-ta-ai-workbench.git#subdirectory=shelf/llm-cost"
```

Part of my QA/TA-with-AI experiments.
