"""Central path resolution — one relocatable base for all mutable state.

Two anchors:
  APP_DIR : the install directory (versioned: config.toml, .env, frontend, code).
            Fixed, derived from this file's location.
  home()  : base for mutable / secret state (data, logs, sessions, credentials).
            Env ``QATAKI_HOME`` overrides it; the default is ``APP_DIR`` so an
            existing ``data/`` and ``logs/`` stay exactly where they are
            (back-compatible). Set ``QATAKI_HOME=/srv/qataki`` to relocate the
            whole mutable tree at once for a real deployment.

All modules anchor their files through this module instead of each computing
``parents[2]`` on their own — which also fixes the post-restructure bug where a
``.git``-walk landed at the workbench root instead of the app folder.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]


def home() -> Path:
    env = os.environ.get("QATAKI_HOME")
    return Path(env).expanduser().resolve() if env else APP_DIR


def config_file() -> Path:
    return APP_DIR / "config.toml"          # versioned — stays in the install dir


def data_dir() -> Path:
    return home() / "data"


def logs_dir() -> Path:
    return home() / "logs"


def sessions_dir() -> Path:
    return data_dir() / "sessions"


def artifacts_dir() -> Path:
    return data_dir() / "artifacts"


def projects_dir() -> Path:
    return data_dir() / "projects"


def context_dir() -> Path:
    """Benutzer-/agent-editierte Prompts & Skills (Override vor Paket-Default)."""
    return data_dir() / "context"


def credentials_file() -> Path:
    return home() / "credentials.yaml"


def ensure() -> None:
    """Create the mutable directory tree if missing (idempotent)."""
    for d in (data_dir(), logs_dir(), sessions_dir(), artifacts_dir(),
              context_dir() / "prompts", context_dir() / "skills"):
        d.mkdir(parents=True, exist_ok=True)
