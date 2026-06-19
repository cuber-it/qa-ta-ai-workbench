"""
Programm-Konfiguration (config.toml im Repo-Wurzelverzeichnis).

Liefert Default-Werte, die beim Anlegen neuer Projekte und Runs vorbelegt
werden. Fehlt die Datei oder ein einzelner Wert, greifen die eingebauten
Fallbacks. Die Datei wird bei jedem Zugriff frisch gelesen, damit Aenderungen
ohne Neustart wirken.
"""
import tomllib

from . import paths

CONFIG_PATH = paths.config_file()

_PROJECT_DEFAULTS = {
    "base_url": "",
    "description": "",
    "artifacts_base": "~/.qataki",
    "default_provider": "",
}
_RUN_DEFAULTS = {
    "headless": True,
}


def load() -> dict:
    if CONFIG_PATH.is_file():
        try:
            with CONFIG_PATH.open("rb") as f:
                return tomllib.load(f)
        except Exception:
            pass
    return {}


def _section(name: str, fallback: dict) -> dict:
    cfg = load().get(name, {})
    out = dict(fallback)
    for k in out:
        if k in cfg:
            out[k] = cfg[k]
    return out


def project_defaults() -> dict:
    return _section("project_defaults", _PROJECT_DEFAULTS)


def run_defaults() -> dict:
    return _section("run_defaults", _RUN_DEFAULTS)


def llm() -> dict:
    """Roh-Sektion [llm]. Die Default-Basis liegt in settings_store.DEFAULTS."""
    return load().get("llm", {})


def budget() -> dict:
    """Roh-Sektion [budget]. Die Default-Basis liegt in cost_guard.CostLimits."""
    return load().get("budget", {})
