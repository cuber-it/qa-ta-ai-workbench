"""
uc-llm-provider Server — Config

Lädt aus ENV oder config.yaml.
Priorität: CLI-Args > ENV > YAML > Default
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from ..logging.cost_logger import LogMode


@dataclass
class ServerConfig:
    provider:  str
    model:     str
    api_key:   str
    api_base:  str
    log_mode:  LogMode  # sqlite | jsonl | none
    log_dir:   str
    port:      int
    host:      str   = "0.0.0.0"
    cors_origins: list[str] = field(default_factory=lambda: ["*"])

    def to_provider_config(self) -> dict:
        cfg = {
            "name":          self.provider,
            "provider_type": self.provider,
            "default_model": self.model,
            "api_key":       self.api_key,
        }
        if self.api_base:
            cfg["api_base"] = self.api_base
        return cfg


def load_config(
    port:      int,
    provider:  Optional[str] = None,
    model:     Optional[str] = None,
    api_key:   Optional[str] = None,
    api_base:  Optional[str] = None,
    log_mode:  Optional[str] = None,
    log_dir:   Optional[str] = None,
    config_file: Optional[str] = None,
) -> ServerConfig:
    """
    Baut ServerConfig aus CLI-Args + ENV + optionaler YAML.
    CLI-Args haben Vorrang, ENV danach, YAML zuletzt.
    """
    yaml_cfg: dict = {}
    if config_file and Path(config_file).exists():
        with open(config_file, encoding="utf-8") as f:
            yaml_cfg = yaml.safe_load(f) or {}

    def resolve(cli_val, env_key, yaml_key, default=""):
        if cli_val:
            return cli_val
        env_val = os.environ.get(env_key, "")
        if env_val:
            return env_val
        return yaml_cfg.get(yaml_key, default)

    return ServerConfig(
        port      = port,
        provider  = resolve(provider,  "UC_LLM_PROVIDER", "provider",  "openai"),
        model     = resolve(model,     "UC_LLM_MODEL",    "model",     "gpt-4o-mini"),
        api_key   = resolve(api_key,   "UC_LLM_API_KEY",  "api_key",   ""),
        api_base  = resolve(api_base,  "UC_LLM_API_BASE", "api_base",  ""),
        log_mode  = resolve(log_mode,  "UC_LLM_LOG_MODE", "log_mode",  "sqlite"),
        log_dir   = resolve(log_dir,   "UC_LLM_LOG_DIR",  "log_dir",   "./logs"),
        host      = yaml_cfg.get("host", "0.0.0.0"),
        cors_origins = yaml_cfg.get("cors_origins", ["*"]),
    )
