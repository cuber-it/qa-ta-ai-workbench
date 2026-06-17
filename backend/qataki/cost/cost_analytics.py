"""
Cost-Analytics ueber die llm_costs-Tabelle (uc-llm-provider Cost-Logger).

Die Provider-Tabelle speichert nur Tokens, kein Geld. USD wird hier pro
(provider, model)-Gruppe via pricing berechnet -- eine Quelle der Wahrheit,
keine Doppel-Buchhaltung. Read-only-Zugriff; fehlt die DB, kommen leere
Ergebnisse zurueck.

Hinweis: abgebrochene Calls (NOTAUS) koennen lokal mit 0 Tokens geloggt
sein und untertreiben dann die echten Serverkosten.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from qataki.cost import pricing


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    return here.parents[3]


_DB_PATH = _repo_root() / "logs" / "llm_costs.sqlite3"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _where(period: str | None) -> tuple[str, list]:
    """Baut die WHERE-Klausel fuer eine Periode auf Basis der ts-Spalte (ISO/UTC)."""
    now = datetime.now(timezone.utc)
    if not period or period == "all":
        return "", []
    if period == "today":
        return "WHERE ts LIKE ?", [now.strftime("%Y-%m-%d") + "%"]
    if period == "month":
        return "WHERE ts LIKE ?", [now.strftime("%Y-%m") + "%"]
    if period == "week":
        monday = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        return "WHERE ts >= ?", [monday]
    if len(period) == 7 and period.count("-") == 1:    # YYYY-MM
        return "WHERE ts LIKE ?", [period + "%"]
    if len(period) == 10 and period.count("-") == 2:   # YYYY-MM-DD
        return "WHERE ts LIKE ?", [period + "%"]
    return "", []


def _rows(period: str | None, provider: str | None = None) -> list[dict]:
    where, params = _where(period)
    if provider:
        where = (where + " AND " if where else "WHERE ") + "provider = ?"
        params = params + [provider]
    sql = f"""
        SELECT provider, model,
               COALESCE(SUM(input_tokens), 0)  AS in_tok,
               COALESCE(SUM(output_tokens), 0) AS out_tok,
               COALESCE(SUM(total_tokens), 0)  AS tot_tok,
               COUNT(*)                        AS calls
        FROM llm_costs {where}
        GROUP BY provider, model
    """
    try:
        conn = _connect()
    except sqlite3.OperationalError:
        return []
    try:
        raw = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    out = []
    for r in raw:
        cost = pricing.calculate_cost(r["model"], r["in_tok"], r["out_tok"])
        out.append({
            "provider":      r["provider"] or "unknown",
            "model":         r["model"],
            "input_tokens":  r["in_tok"],
            "output_tokens": r["out_tok"],
            "total_tokens":  r["tot_tok"],
            "calls":         r["calls"],
            "cost_usd":      round(cost, 6),
        })
    return out


def by_model(period: str | None = "month", provider: str | None = None) -> list[dict]:
    return sorted(_rows(period, provider), key=lambda x: x["cost_usd"], reverse=True)


def by_provider(period: str | None = "month") -> list[dict]:
    agg: dict[str, dict] = {}
    for r in _rows(period):
        p = agg.setdefault(r["provider"], {
            "provider": r["provider"], "input_tokens": 0, "output_tokens": 0,
            "total_tokens": 0, "calls": 0, "cost_usd": 0.0,
        })
        p["input_tokens"]  += r["input_tokens"]
        p["output_tokens"] += r["output_tokens"]
        p["total_tokens"]  += r["total_tokens"]
        p["calls"]         += r["calls"]
        p["cost_usd"]      += r["cost_usd"]
    out = list(agg.values())
    for p in out:
        p["cost_usd"] = round(p["cost_usd"], 6)
    return sorted(out, key=lambda x: x["cost_usd"], reverse=True)


def totals(period: str | None = "month") -> dict:
    rows = _rows(period)
    return {
        "period":        period or "all",
        "input_tokens":  sum(r["input_tokens"]  for r in rows),
        "output_tokens": sum(r["output_tokens"] for r in rows),
        "total_tokens":  sum(r["total_tokens"]  for r in rows),
        "calls":         sum(r["calls"]         for r in rows),
        "cost_usd":      round(sum(r["cost_usd"] for r in rows), 6),
    }


def overview(period: str | None = "month") -> dict:
    return {
        "totals":      totals(period),
        "by_provider": by_provider(period),
        "by_model":    by_model(period),
    }


def record_estimate(provider: str, model: str, input_tokens: int, output_tokens: int,
                    status: str = "aborted_estimate") -> None:
    """Schreibt eine konservative Schaetzzeile in llm_costs.

    Abgebrochene Calls (NOTAUS) loggt der Provider mit 0 Tokens -> das Budget
    wuerde die echten Serverkosten untertreiben. Diese Zeile traegt den
    Worst-Case (volle max_tokens als Output) nach, damit das Budget eher zu
    hoch als zu niedrig zaehlt.
    """
    from datetime import datetime, timezone
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS llm_costs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, provider TEXT NOT NULL,
            model TEXT NOT NULL, input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0, total_tokens INTEGER NOT NULL DEFAULT 0,
            latency_ms INTEGER NOT NULL DEFAULT 0, caller_id TEXT NOT NULL DEFAULT '',
            session_id TEXT NOT NULL DEFAULT '', task_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'success', error TEXT)""")
        conn.execute(
            "INSERT INTO llm_costs (ts, provider, model, input_tokens, output_tokens, "
            "total_tokens, latency_ms, status) VALUES (?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), provider, model,
             input_tokens, output_tokens, input_tokens + output_tokens, 0, status))
        conn.commit()
    finally:
        conn.close()
