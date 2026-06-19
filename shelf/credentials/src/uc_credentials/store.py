"""Credential store: named login profiles from a project YAML file.

Light and reusable (pydantic + pyyaml only). Passwords are pydantic ``SecretStr``,
so they redact themselves on ``repr``/``str``/logging — the real value is only
reachable via ``.get_secret_value()`` at the point where it is injected (into a
browser context or a form field). Callers reference a profile by its handle
(name); secret values never have to be passed around or shown to a model.

Resolution order per field (highest priority first):
  1. Environment variable  ``QATAKI_CRED__<PROFILE>__<FIELD>``  (CI / scripts)
  2. The YAML store file

The store path is set by the host via ``set_store_path()``, or falls back to the
``UC_CREDENTIALS_FILE`` environment variable. The file is a mapping of profile
name to profile fields, e.g.::

    myapp:
      type: basic
      username: max
      password: s3cret
    shop:
      type: form
      url: https://shop.example/login
      username: max@firma.de
      password: hunter2
      user_field: E-Mail      # label or selector
      pass_field: Passwort
      submit: "role=button[name=Login]"
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, SecretStr

_ENV_PREFIX = "QATAKI_CRED__"
_store_path: Path | None = None


def set_store_path(path: str | os.PathLike | None) -> None:
    """Point the resolver at a project ``credentials.yaml`` (host injection)."""
    global _store_path
    _store_path = Path(path).expanduser() if path else None


def store_path() -> Path | None:
    """The currently configured store path (set_store_path, else env), or None."""
    if _store_path is not None:
        return _store_path
    env = os.environ.get("UC_CREDENTIALS_FILE")
    return Path(env).expanduser() if env else None


class Credential(BaseModel):
    """One login profile. ``type`` drives how it is used; unknown keys are kept
    (``extra='allow'``) so the YAML can grow without code changes."""
    model_config = ConfigDict(extra="allow")

    type: Literal["basic", "form"] = "basic"
    username: str | None = None
    password: SecretStr | None = None
    # form-only, non-secret, SUT-specific (optional):
    url: str | None = None
    user_field: str | None = None
    pass_field: str | None = None
    submit: str | None = None

    def secret(self) -> str:
        """The password's real value. Only call at the injection point."""
        return self.password.get_secret_value() if self.password else ""


def _load_file() -> dict:
    p = store_path()
    if p is None or not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"credentials file is not a mapping of profiles: {p}")
    return data


def _env_overrides(profile: str) -> dict:
    """Collect ``QATAKI_CRED__<PROFILE>__<FIELD>`` overrides for one profile."""
    prefix = f"{_ENV_PREFIX}{profile.upper()}__"
    out: dict = {}
    for key, val in os.environ.items():
        if key.startswith(prefix):
            out[key[len(prefix):].lower()] = val
    return out


def get(profile: str) -> Credential:
    """Resolve a profile (env overrides win over file). Raises KeyError if unknown."""
    raw = dict(_load_file().get(profile) or {})
    raw.update(_env_overrides(profile))
    if not raw:
        raise KeyError(f"unknown credential profile: {profile!r}")
    return Credential(**raw)


def list_profiles() -> list[str]:
    """Profile names only (never values) — safe to surface to an agent."""
    names = set(_load_file().keys())
    for key in os.environ:
        if key.startswith(_ENV_PREFIX):
            name = key[len(_ENV_PREFIX):].split("__", 1)[0]
            if name:
                names.add(name.lower())
    return sorted(names)


def http_credentials(profile: str) -> dict:
    """``{'username', 'password'}`` with REAL values, for Playwright Basic-Auth
    or scripts. Returns secrets — use only at the injection point, never log it
    or hand it to a model."""
    cred = get(profile)
    return {"username": cred.username or "", "password": cred.secret()}
