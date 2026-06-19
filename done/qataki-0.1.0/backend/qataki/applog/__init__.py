"""QATAKI central logging: daily-rotating file, live broadcaster, per-run tagging."""
from .setup import (
    setup,
    set_run,
    clear_run,
    current_run,
    get_logger,
    get_broadcaster,
    set_level,
)
from .reader import read_recent, LEVELS
from .broadcast import LogBroadcaster

__all__ = [
    "setup",
    "set_run",
    "clear_run",
    "current_run",
    "get_logger",
    "get_broadcaster",
    "set_level",
    "read_recent",
    "LEVELS",
    "LogBroadcaster",
]
