"""QATAKI — Quality Assurance, Test Automation, AI."""

__version__ = "0.1.0"

# Wire the extracted cost-core building block (shelf/llm-cost) to this app's
# specifics, so behaviour matches the in-tree version: budget from config.toml,
# the global killswitch, and data/ + logs/ at the repo root.
from pathlib import Path as _Path
from . import config as _config, killswitch as _killswitch
import uc_llm_cost as _cost

_cost.set_data_dir(_Path(__file__).resolve().parents[2])
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
