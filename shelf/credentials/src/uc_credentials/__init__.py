"""uc_credentials — light, reusable credential store (handle -> login profile).

Public API:
    set_store_path(path)      configure the project credentials.yaml (host injection)
    store_path()              the currently configured path (or None)
    get(profile)              -> Credential   (env overrides win over file)
    list_profiles()           -> [str]        names only, safe to show an agent
    http_credentials(profile) -> {'username','password'}  real values, injection only
    Credential                the profile model (password is a redacting SecretStr)
"""
from .store import (
    Credential,
    get,
    http_credentials,
    list_profiles,
    set_store_path,
    store_path,
)

__all__ = [
    "Credential",
    "get",
    "http_credentials",
    "list_profiles",
    "set_store_path",
    "store_path",
]
