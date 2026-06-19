"""Central logging setup: daily-rotating file + live broadcaster, per-run tagging.

setup() attaches two handlers to the root logger: a TimedRotatingFileHandler
(dated file, 7 days kept) for persistence, and a LogBroadcaster for live SSE
streaming. A contextvar carries the active run id into every record via a
LogRecord factory, so both handlers and the UI can filter per run.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from logging.handlers import TimedRotatingFileHandler

from qataki import paths
from .broadcast import LogBroadcaster

LOG_FILE = "qataki.log"
BACKUP_DAYS = 7
DATE_FMT = "%Y-%m-%dT%H:%M:%S"
LINE_FMT = "%(asctime)s\t%(levelname)s\t%(run_id)s\t%(name)s\t%(message)s"

# Eigene Logger, deren INFO/DEBUG ins App-Log sollen (Root bleibt auf WARNING,
# damit Dritt-Bibliotheken nicht fluten).
APP_LOGGERS = (
    "qataki",
    "uc_agent_core",
    "uc_playwright_driver",
    "uc_llm_provider",
    "uc_credentials",
)

_run_id: ContextVar[str | None] = ContextVar("qataki_run_id", default=None)
_configured = False
_broadcaster: LogBroadcaster | None = None
_ts_fmt = logging.Formatter(datefmt=DATE_FMT)


def _record_to_entry(record: logging.LogRecord) -> dict:
    """Shape a record like the file reader's parsed entries."""
    return {
        "ts": _ts_fmt.formatTime(record, DATE_FMT),
        "level": record.levelname,
        "run": getattr(record, "run_id", "-"),
        "name": record.name,
        "msg": record.getMessage(),
    }


def _install_run_factory() -> None:
    old = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        rec = old(*args, **kwargs)
        rec.run_id = _run_id.get() or "-"
        return rec

    logging.setLogRecordFactory(factory)


def setup(level: int = logging.DEBUG) -> None:
    """Idempotently attach file + broadcast handlers to the root logger."""
    global _configured, _broadcaster
    if _configured:
        return
    paths.ensure()
    _install_run_factory()

    file_handler = TimedRotatingFileHandler(
        paths.logs_dir() / LOG_FILE,
        when="midnight",
        backupCount=BACKUP_DAYS,
        encoding="utf-8",
        utc=False,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LINE_FMT, datefmt=DATE_FMT))

    _broadcaster = LogBroadcaster(maxsize=1000, record_to_payload=_record_to_entry)
    _broadcaster.setLevel(logging.DEBUG)

    root = logging.getLogger()
    root.addHandler(file_handler)
    root.addHandler(_broadcaster)
    for name in APP_LOGGERS:
        logging.getLogger(name).setLevel(level)
    _configured = True


def get_broadcaster() -> LogBroadcaster | None:
    return _broadcaster


_LEVEL_NAMES = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
}


def set_level(level) -> None:
    """Set the level of the app loggers. Accepts an int or a name string.

    The file/broadcast handlers stay at DEBUG; this only gates which records the
    app loggers emit, so a future system-config switch can change verbosity live.
    """
    if isinstance(level, str):
        level = _LEVEL_NAMES.get(level.strip().upper(), logging.INFO)
    for name in APP_LOGGERS:
        logging.getLogger(name).setLevel(level)


def set_run(run_id: str | None) -> None:
    """Tag all subsequent log records in this context with ``run_id``."""
    _run_id.set(run_id or None)


def clear_run() -> None:
    _run_id.set(None)


def current_run() -> str | None:
    return _run_id.get()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
