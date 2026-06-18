"""Tests for uc-llm-cost: limit layering, guard behaviour, injection, pricing."""
import pytest

import uc_llm_cost as C
from uc_llm_cost import CostGuard, CostLimits, CostLimitExceeded, RunCosts, pricing, pricing_store


@pytest.fixture(autouse=True)
def _reset(tmp_path):
    # Standalone defaults for every test; data/logs go to an isolated tmp dir.
    C.set_config_loader(lambda: {})
    C.set_killswitch(lambda: False)
    C.set_data_dir(tmp_path)
    yield


# ── Limit-Schichtung ─────────────────────────────────────────────────────────

def test_default_hard_limit():
    assert CostLimits.from_env().hard_tokens_per_run == 50_000


def test_config_injection_overrides_default():
    C.set_config_loader(lambda: {"max_tokens_per_run": 12_345})
    assert CostLimits.from_env().hard_tokens_per_run == 12_345


def test_ui_override_wins_over_config(tmp_path):
    C.set_config_loader(lambda: {"max_tokens_per_run": 12_345})
    C.save_overrides({"max_tokens_per_run": 77_000})
    assert (tmp_path / "data" / "budget.json").is_file()
    assert C.load_overrides()["max_tokens_per_run"] == 77_000
    assert CostLimits.from_env().hard_tokens_per_run == 77_000


# ── Guard-Verhalten ──────────────────────────────────────────────────────────

def _guard_with(**limits):
    C.set_config_loader(lambda: limits)
    return CostGuard()


def test_soft_then_sparmode_warnings():
    g = _guard_with(max_tokens_per_run=1000, soft_tokens_per_run=100, sparmode_tokens=200)
    costs = RunCosts()
    costs.add(150, 0)
    levels = [w.level for w in g.check(costs)]
    assert "warn" in levels and "sparmode" not in levels
    costs.add(100, 0)                     # -> 250, ueber sparmode
    levels2 = [w.level for w in g.check(costs)]
    assert "sparmode" in levels2
    assert g.sparmode is True


def test_hard_token_limit_raises():
    g = _guard_with(max_tokens_per_run=200)
    costs = RunCosts()
    costs.add(200, 0)
    with pytest.raises(CostLimitExceeded):
        g.check(costs)


def test_killswitch_raises():
    C.set_killswitch(lambda: True)
    g = CostGuard()
    with pytest.raises(CostLimitExceeded) as ei:
        g.check(RunCosts())
    assert "NOTAUS" in ei.value.reason


def test_record_llm_call_accumulates():
    g = CostGuard()
    costs = RunCosts()
    warns = g.record_llm_call(costs, 100, 50, model="gpt-4o-mini")
    assert costs.tokens == 150
    assert costs.llm_calls == 1
    assert isinstance(warns, list)


# ── Pricing ──────────────────────────────────────────────────────────────────

def test_pricing_table_and_calc():
    models = pricing.list_models()
    assert isinstance(models, dict) and models
    model = next(iter(pricing.PRICING))
    assert pricing.calculate_cost(model, 1000, 1000) > 0
    rate = pricing.get_rates(model)
    assert isinstance(rate, tuple) and len(rate) == 2


def test_pricing_store_roundtrip():
    store = pricing_store.load()
    assert isinstance(store, dict)
    pricing_store.save(store)             # darf nicht werfen, schreibt nach data/pricing.json
    assert isinstance(pricing_store.load(), dict)
