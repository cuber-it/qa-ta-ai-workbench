"""test_cost_logger.py — SQLite und JSONL Logging."""
import tempfile
from pathlib import Path

import pytest

from uc_llm_provider.logging.cost_logger import CostLogger, reset_cost_logger


@pytest.fixture(autouse=True)
def reset():
    reset_cost_logger()
    yield
    reset_cost_logger()


def test_sqlite_logger_creates_db():
    with tempfile.TemporaryDirectory() as tmp:
        CostLogger(log_dir=tmp, mode="sqlite")
        assert (Path(tmp) / "llm_costs.sqlite3").exists()


def test_sqlite_logger_writes_record():
    with tempfile.TemporaryDirectory() as tmp:
        logger = CostLogger(log_dir=tmp, mode="sqlite")
        logger.log(
            provider="openai", model="gpt-4o-mini",
            input_tokens=10, output_tokens=5,
            latency_ms=120, caller_id="test", status="success",
        )
        rows = logger.query("SELECT * FROM llm_costs")
        assert len(rows) == 1
        assert rows[0]["provider"] == "openai"
        assert rows[0]["total_tokens"] == 15
        assert rows[0]["latency_ms"] == 120


def test_sqlite_logger_summary():
    with tempfile.TemporaryDirectory() as tmp:
        logger = CostLogger(log_dir=tmp, mode="sqlite")
        for _ in range(3):
            logger.log(provider="openai", model="gpt-4o-mini",
                       input_tokens=10, output_tokens=5)
        logger.log(provider="anthropic", model="claude-sonnet",
                   input_tokens=20, output_tokens=10)
        summary = logger.summary()
        assert "by_model" in summary
        models = [r["model"] for r in summary["by_model"]]
        assert "gpt-4o-mini" in models
        assert "claude-sonnet" in models


def test_jsonl_logger_writes_file():
    with tempfile.TemporaryDirectory() as tmp:
        logger = CostLogger(log_dir=tmp, mode="jsonl")
        logger.log(provider="openai", model="gpt-4o-mini",
                   input_tokens=10, output_tokens=5)
        path = Path(tmp) / "llm_costs.jsonl"
        assert path.exists()
        import json
        record = json.loads(path.read_text().strip())
        assert record["provider"] == "openai"
        assert record["total_tokens"] == 15


def test_none_logger_does_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        logger = CostLogger(log_dir=tmp, mode="none")
        logger.log(provider="openai", model="gpt-4o-mini",
                   input_tokens=10, output_tokens=5)
        assert not (Path(tmp) / "llm_costs.sqlite3").exists()
        assert not (Path(tmp) / "llm_costs.jsonl").exists()


def test_sqlite_query_returns_empty_on_jsonl_mode():
    with tempfile.TemporaryDirectory() as tmp:
        logger = CostLogger(log_dir=tmp, mode="jsonl")
        result = logger.query("SELECT 1")
        assert result == []
