"""
PricingStore — persistente Tarif-Verwaltung.
Speichert Preise in data/pricing.json (editierbar, versionierbar).
Fällt auf pricing.py zurück wenn keine JSON-Datei vorhanden.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


from . import _paths


def _store_path() -> Path:
    return _paths.data("pricing.json")

# Provider die kostenlos sind — kein Pricing-Check nötig
FREE_PROVIDERS = {"scan", "ollama", "openai_compatible", "lm_studio"}


def _default_store() -> dict:
    """Initialer Store aus pricing.py."""
    from .pricing import PRICING
    return {
        "updated_at":    None,
        "update_source": "builtin",
        "pending_diff":  None,
        "prices": {
            model: {"prompt": rates[0], "completion": rates[1]}
            for model, rates in PRICING.items()
        },
    }


def load() -> dict:
    """Lädt Store aus JSON, fällt auf Defaults zurück."""
    if _store_path().exists():
        try:
            return json.loads(_store_path().read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("PricingStore: JSON corrupt, using defaults: %s", e)
    return _default_store()


def save(store: dict) -> None:
    _store_path().parent.mkdir(parents=True, exist_ok=True)
    _store_path().write_text(
        json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_rates(model: str) -> tuple[float, float]:
    """Gibt (prompt_per_mtok, completion_per_mtok) zurück."""
    store = load()
    prices = store.get("prices", {})
    if model in prices:
        p = prices[model]
        return (p["prompt"], p["completion"])
    # Präfix-Suche
    for key, p in prices.items():
        if model.startswith(key) or key.startswith(model.split("-")[0]):
            return (p["prompt"], p["completion"])
    return (1.00, 3.00)  # konservative Schätzung


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates = get_rates(model)
    return (prompt_tokens / 1_000_000) * rates[0] + \
           (completion_tokens / 1_000_000) * rates[1]


def set_pending_diff(diff: list[dict]) -> None:
    store = load()
    store["pending_diff"] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "changes":    diff,
    }
    save(store)


def get_pending_diff() -> dict | None:
    return load().get("pending_diff")


def apply_diff(diff: list[dict]) -> None:
    store = load()
    for change in diff:
        model = change["model"]
        store["prices"][model] = {
            "prompt":     change["new_prompt"],
            "completion": change["new_completion"],
        }
    store["pending_diff"] = None
    store["updated_at"]    = datetime.now(timezone.utc).isoformat()
    store["update_source"] = "pricing_agent"
    save(store)


def reject_pending_diff() -> None:
    """Verwirft den anstehenden Diff ohne ihn anzuwenden."""
    store = load()
    store["pending_diff"] = None
    save(store)


def status() -> dict:
    store = load()
    return {
        "updated_at":    store.get("updated_at"),
        "update_source": store.get("update_source", "builtin"),
        "model_count":   len(store.get("prices", {})),
        "pending_diff":  store.get("pending_diff") is not None,
        "pending_count": len((store.get("pending_diff") or {}).get("changes", [])),
        "store_path":    str(_store_path()),
    }


def is_free_provider(provider: str) -> bool:
    return provider.lower() in FREE_PROVIDERS
