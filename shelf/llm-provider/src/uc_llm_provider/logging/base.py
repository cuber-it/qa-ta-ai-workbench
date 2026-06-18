"""
uc-llm-provider — JsonlLogger Basisklasse
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

_log = logging.getLogger(__name__)


class JsonlLogger:
    def __init__(self, path: str | Path, enabled: bool = True):
        self.enabled = enabled
        self._path   = Path(path)
        if enabled:
            self._path.parent.mkdir(parents=True, exist_ok=True)

    def _ts(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _write(self, record: dict) -> None:
        if not self.enabled:
            return
        try:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            _log.warning("Log write failed (%s): %s", self._path, e)
