"""QATAKI — Quality Assurance, Test Automation, AI."""

__version__ = "0.1.0"

# Wire the extracted cost-core building block (shelf/llm-cost) to this app's
# specifics, so behaviour matches the in-tree version: budget from config.toml,
# the global killswitch, and data/ + logs/ under the relocatable QATAKI_HOME.
from . import paths as _paths, config as _config, killswitch as _killswitch
import uc_llm_cost as _cost

_paths.ensure()                       # create data/, logs/, sessions/ if missing
_cost.set_data_dir(_paths.home())
_cost.set_config_loader(_config.budget)
_cost.set_killswitch(_killswitch.is_active)

# Wire the extracted agent-core (shelf/agent-core) to this app's services.
from . import settings_store as _settings_store, llm as _llm, cancellation as _cancellation, mcp_client as _mcp_client
import uc_agent_core as _agent

_agent.set_killswitch(_killswitch.is_active)
_agent.set_settings_loader(_settings_store.load)
_agent.set_llm(_llm)
_agent.set_cancellation(_cancellation)
_agent.set_mcp_client(_mcp_client)

# Token-Verbrauchslog (logs/token-usage.log) an den Loop haengen.
from . import usagelog as _usagelog
_agent.set_usage_sink(_usagelog.record)

# Kontext-Overrides (editierte Prompts & Skills) unter home/data/context.
_agent.set_context_dir(_paths.context_dir())

# Agent-Skilling protokollieren: Aenderungen des Agenten an Skills landen mit
# Akteur 'agent' und aktueller run_id im Kontext-Changelog.
from . import applog as _applog, context_audit as _context_audit
_agent.set_context_audit_sink(
    lambda action, target, summary: _context_audit.record(
        "agent", action, target, summary, run_id=_applog.current_run()))

# Wire the credential store (shelf/credentials): credentials.yaml under
# QATAKI_HOME (git-ignored). Env QATAKI_CRED__<PROFILE>__<FIELD> still wins.
import uc_credentials as _creds

_creds.set_store_path(_paths.credentials_file())
