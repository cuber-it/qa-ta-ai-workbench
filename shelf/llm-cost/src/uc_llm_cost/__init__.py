"""uc-llm-cost — LLM cost guard, pricing table, and usage analytics.

A generic building block with no application coupling. The host app wires three
things; all have safe defaults so the package also works standalone:

    import uc_llm_cost
    uc_llm_cost.set_data_dir(repo_root)           # where data/ and logs/ live
    uc_llm_cost.set_config_loader(my_budget_fn)   # returns the [budget] config dict
    uc_llm_cost.set_killswitch(my_killswitch_fn)  # returns True to hard-stop
"""
from . import _paths, cost_guard, pricing, pricing_store, cost_analytics
from .cost_guard import (
    CostGuard, CostLimits, CostWarning, CostLimitExceeded, RunCosts,
    load_overrides, save_overrides,
)

__all__ = [
    "cost_guard", "pricing", "pricing_store", "cost_analytics",
    "CostGuard", "CostLimits", "CostWarning", "CostLimitExceeded", "RunCosts",
    "load_overrides", "save_overrides",
    "set_data_dir", "set_config_loader", "set_killswitch",
]


def set_data_dir(path) -> None:
    """Base directory for data/budget.json, data/pricing.json and logs/*."""
    from pathlib import Path
    _paths.base_dir = Path(path)


def set_config_loader(fn) -> None:
    """Callable returning the [budget] config dict (layered below env/UI). Default: empty."""
    cost_guard._config_loader = fn


def set_killswitch(fn) -> None:
    """Callable returning True when execution must hard-stop. Default: never active."""
    cost_guard._killswitch = fn
