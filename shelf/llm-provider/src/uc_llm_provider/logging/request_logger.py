"""
uc-llm-provider — Request/Response Logger
"""
from pathlib import Path

from .base import JsonlLogger


class RequestResponseLogger(JsonlLogger):

    def __init__(self, provider: str, log_dir: str = "./logs", enabled: bool = True):
        super().__init__(
            path=Path(log_dir) / f"{provider}_requests.jsonl",
            enabled=enabled,
        )
        self.provider = provider

    def log_request(self, endpoint: str, payload: dict,
                    session_id: str = "", caller_id: str = "", task_id: str = "") -> None:
        self._write({
            "ts": self._ts(), "direction": "request",
            "provider": self.provider, "endpoint": endpoint,
            "session_id": session_id, "caller_id": caller_id, "task_id": task_id,
            "payload": payload,
        })

    def log_response(self, endpoint: str, status: int, body: dict,
                     session_id: str = "", caller_id: str = "", task_id: str = "") -> None:
        self._write({
            "ts": self._ts(), "direction": "response",
            "provider": self.provider, "endpoint": endpoint, "status": status,
            "session_id": session_id, "caller_id": caller_id, "task_id": task_id,
            "body": body,
        })

    def log_error(self, endpoint: str, error: str,
                  session_id: str = "", caller_id: str = "", task_id: str = "") -> None:
        self._write({
            "ts": self._ts(), "direction": "error",
            "provider": self.provider, "endpoint": endpoint, "error": error,
            "session_id": session_id, "caller_id": caller_id, "task_id": task_id,
        })
