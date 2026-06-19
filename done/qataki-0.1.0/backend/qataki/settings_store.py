"""Persistente LLM-Einstellungen.

Schichtung: eingebaute DEFAULTS  <-  config.toml [llm]  <-  data/settings.json.
settings.json haelt nur die Abweichungen vom Config-Default (sparse); die
Settings-UI schreibt ueber save(). Was in settings.json fehlt, kommt aus der
Config, was dort fehlt, aus den eingebauten Fallbacks.
"""
import json

from . import config, paths

STORE = paths.data_dir() / "settings.json"

DEFAULTS = {
    "provider_type": "anthropic",
    "model": "",          # leer = Provider-Default
    "max_tokens": 1024,
    "temperature": 0.7,
    # Agent-Settings (eigene Lauf-Parameter, gleicher Provider/Model)
    "agent_max_tokens": 16384,
    "agent_temperature": 0.3,
    "agent_max_iterations": 15,
    # Logging: DEBUG | INFO | WARNING | ERROR (per System-Config aenderbar)
    "log_level": "DEBUG",
    # Token-Verbrauchslog (logs/token-usage.log) an/aus, Default aktiviert
    "token_log": True,
}


def _base() -> dict:
    """DEFAULTS, ueberlagert mit config.toml [llm] (nur bekannte Schluessel)."""
    base = dict(DEFAULTS)
    for k, v in config.llm().items():
        if k in DEFAULTS:
            base[k] = v
    return base


def _overrides() -> dict:
    if STORE.is_file():
        try:
            raw = json.loads(STORE.read_text("utf-8"))
            return {k: v for k, v in raw.items() if k in DEFAULTS}
        except Exception:
            pass
    return {}


def load() -> dict:
    return {**_base(), **_overrides()}


def save(data: dict) -> dict:
    base = _base()
    ov = _overrides()
    for k in DEFAULTS:
        if k in data and data[k] is not None:
            ov[k] = data[k]
    # sparse: nur Abweichungen vom Config-Default behalten
    sparse = {k: v for k, v in ov.items() if v != base[k]}
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(sparse, indent=2), "utf-8")
    return {**base, **sparse}
