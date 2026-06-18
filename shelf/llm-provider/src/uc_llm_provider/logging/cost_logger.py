"""
uc-llm-provider — Cost Logger
Default: SQLite (querybar, aggregierbar).
Alternativ: JSONL oder none.
"""
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

_instance: "CostLogger | None" = None
_log = logging.getLogger(__name__)

LogMode = Literal["sqlite", "jsonl", "none"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_costs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT    NOT NULL,
    provider      TEXT    NOT NULL,
    model         TEXT    NOT NULL,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens  INTEGER NOT NULL DEFAULT 0,
    latency_ms    INTEGER NOT NULL DEFAULT 0,
    caller_id     TEXT    NOT NULL DEFAULT '',
    session_id    TEXT    NOT NULL DEFAULT '',
    task_id       TEXT    NOT NULL DEFAULT '',
    status        TEXT    NOT NULL DEFAULT 'success',
    error         TEXT
);
CREATE INDEX IF NOT EXISTS idx_llm_costs_ts       ON llm_costs(ts);
CREATE INDEX IF NOT EXISTS idx_llm_costs_provider ON llm_costs(provider);
CREATE INDEX IF NOT EXISTS idx_llm_costs_model    ON llm_costs(model);
"""


class CostLogger:

    def __init__(self, log_dir: str = "./logs", mode: LogMode = "sqlite"):
        self.mode    = mode
        self.enabled = mode != "none"
        if not self.enabled:
            return

        self._dir = Path(log_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

        if mode == "sqlite":
            self._db_path = self._dir / "llm_costs.sqlite3"
            self._init_db()
        elif mode == "jsonl":
            self._jsonl_path = self._dir / "llm_costs.jsonl"

    def _init_db(self) -> None:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.executescript(_SCHEMA)
        except Exception as e:
            _log.warning("CostLogger DB init failed: %s", e)

    def _ts(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def log(
        self,
        provider:      str,
        model:         str,
        input_tokens:  int,
        output_tokens: int,
        latency_ms:    int  = 0,
        caller_id:     str  = "",
        session_id:    str  = "",
        task_id:       str  = "",
        status:        str  = "success",
        error_message: str | None = None,
    ) -> None:
        if not self.enabled:
            return

        ts    = self._ts()
        total = input_tokens + output_tokens

        if self.mode == "sqlite":
            self._write_sqlite(ts, provider, model, input_tokens, output_tokens, total,
                               latency_ms, caller_id, session_id, task_id, status, error_message)
        elif self.mode == "jsonl":
            self._write_jsonl(ts, provider, model, input_tokens, output_tokens, total,
                              latency_ms, caller_id, session_id, task_id, status, error_message)

    def _write_sqlite(self, ts, provider, model, in_tok, out_tok, total,
                      ms, caller_id, session_id, task_id, status, error) -> None:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """INSERT INTO llm_costs
                       (ts, provider, model, input_tokens, output_tokens, total_tokens,
                        latency_ms, caller_id, session_id, task_id, status, error)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (ts, provider, model, in_tok, out_tok, total,
                     ms, caller_id, session_id, task_id, status, error),
                )
        except Exception as e:
            _log.warning("CostLogger SQLite write failed: %s", e)

    def _write_jsonl(self, ts, provider, model, in_tok, out_tok, total,
                     ms, caller_id, session_id, task_id, status, error) -> None:
        record = {
            "ts": ts, "provider": provider, "model": model,
            "input_tokens": in_tok, "output_tokens": out_tok, "total_tokens": total,
            "latency_ms": ms, "caller_id": caller_id, "session_id": session_id,
            "task_id": task_id, "status": status,
        }
        if error:
            record["error"] = error
        try:
            with self._jsonl_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            _log.warning("CostLogger JSONL write failed: %s", e)


    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Executes arbitrary SELECT on the cost DB. SQLite mode only."""
        if self.mode != "sqlite":
            return []
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                return [dict(r) for r in conn.execute(sql, params).fetchall()]
        except Exception as e:
            _log.warning("CostLogger query failed: %s", e)
            return []

    def summary(self) -> dict:
        """Aggregated summary: total calls, tokens, by provider/model."""
        if self.mode != "sqlite":
            return {}
        rows = self.query("""
            SELECT provider, model,
                   COUNT(*)            AS calls,
                   SUM(total_tokens)   AS tokens,
                   AVG(latency_ms)     AS avg_latency_ms
            FROM llm_costs
            GROUP BY provider, model
            ORDER BY tokens DESC
        """)
        return {"by_model": rows}


def get_cost_logger(mode: LogMode | None = None) -> CostLogger:
    """
    Singleton. Beim ersten Aufruf wird der Mode aus ENV gelesen wenn nicht angegeben.
    Danach wird dieselbe Instanz zurückgegeben.
    """
    global _instance
    if _instance is None:
        if mode is None:
            env_mode = os.environ.get("UC_LLM_LOG_MODE", "sqlite").lower()
            mode = env_mode if env_mode in ("sqlite", "jsonl", "none") else "sqlite"
        log_dir   = os.environ.get("UC_LLM_LOG_DIR", "./logs")
        _instance = CostLogger(log_dir=log_dir, mode=mode)
    return _instance


def reset_cost_logger() -> None:
    """Reset singleton — für Tests."""
    global _instance
    _instance = None
