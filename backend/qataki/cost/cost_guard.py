"""
CostGuard — Kostenkontrolle auf allen Ebenen.

Ebene 1: Hard-Limit pro Run (Token + USD)   -> Run wird abgebrochen
Ebene 2: Soft-Limit pro Run (80%)           -> Warnung
Ebene 3: Sparmode (90%)                      -> kuerzere Prompts
Ebene 4: Tages-/Monatsbudget                 -> Run wird gesperrt
Ebene 5: Audit-Log                           -> jeder Verbrauch protokolliert

Budget-Zahlen kommen aus cost_analytics (Quelle: llm_costs-Tabelle, € via
pricing). NIEMALS still ueberschreiten -- immer explizit stoppen oder warnen.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .. import config

log = logging.getLogger(__name__)


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    return here.parents[3]


_AUDIT_PATH = _repo_root() / "logs" / "cost_audit.jsonl"


class CostLimitExceeded(Exception):
    def __init__(self, reason: str, costs: "RunCosts | None" = None):
        super().__init__(reason)
        self.reason = reason
        self.costs  = costs


class CostWarning:
    """Nicht-fatale Warnung -- Run laeuft weiter, UI wird benachrichtigt."""
    def __init__(self, reason: str, level: str = "warn"):
        self.reason = reason
        self.level  = level  # warn | sparmode


@dataclass
class RunCosts:
    tokens:            int   = 0
    llm_calls:         int   = 0
    cost_usd:          float = 0.0
    prompt_tokens:     int   = 0
    completion_tokens: int   = 0

    def add(self, prompt: int, completion: int, usd: float = 0.0) -> None:
        self.prompt_tokens     += prompt
        self.completion_tokens += completion
        self.tokens            += prompt + completion
        self.llm_calls         += 1
        self.cost_usd          += usd

    def to_dict(self) -> dict:
        return {
            "tokens":            self.tokens,
            "prompt_tokens":     self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "llm_calls":         self.llm_calls,
            "cost_usd":          round(self.cost_usd, 6),
        }


REPO = Path(__file__).resolve().parents[3]
_OVERRIDE_STORE = REPO / "data" / "budget.json"

# Editierbare Budget-Schluessel (UI) -> Cast
_BUDGET_CASTS = {
    "max_tokens_per_run": int, "soft_tokens_per_run": int, "sparmode_tokens": int,
    "max_usd_per_run": float, "max_tokens_per_day": int, "max_usd_per_day": float,
    "max_usd_per_month": float, "confirm_above_usd": float,
}


def load_overrides() -> dict:
    """UI-Overrides (data/budget.json) — oberste Schicht ueber Config/Env."""
    if _OVERRIDE_STORE.is_file():
        try:
            raw = json.loads(_OVERRIDE_STORE.read_text("utf-8"))
            return {k: v for k, v in raw.items() if k in _BUDGET_CASTS}
        except Exception:
            pass
    return {}


def save_overrides(fields: dict) -> dict:
    """Overrides mergen + persistieren. Greift beim naechsten Run (Guard je Run neu)."""
    ov = load_overrides()
    for k, cast in _BUDGET_CASTS.items():
        if k in fields and fields[k] is not None:
            try:
                ov[k] = cast(fields[k])
            except Exception:
                pass
    _OVERRIDE_STORE.parent.mkdir(parents=True, exist_ok=True)
    _OVERRIDE_STORE.write_text(json.dumps(ov, indent=2), "utf-8")
    return ov


@dataclass
class CostLimits:
    """Alle Limits auf einen Blick. Aus Env geladen."""
    hard_tokens_per_run:    int   = 50_000
    soft_tokens_per_run:    int   = 40_000
    sparmode_tokens:        int   = 45_000
    hard_usd_per_run:       float = 1.00
    hard_tokens_per_day:    int   = 500_000
    hard_usd_per_day:       float = 5.00
    hard_usd_per_month:     float = 50.00
    confirm_above_usd:      float = 0.10

    @classmethod
    def from_env(cls) -> "CostLimits":
        """Schichtung: Defaults < config.toml [budget] < Env < data/budget.json (UI)."""
        cfg = config.budget()
        ov = load_overrides()

        def pick(cfg_key, env_key, default, cast):
            val = default
            if cfg_key in cfg:
                try:
                    val = cast(cfg[cfg_key])
                except Exception:
                    pass
            env = os.getenv(env_key)
            if env not in (None, ""):
                try:
                    val = cast(env)
                except Exception:
                    pass
            if cfg_key in ov:                 # UI-Override hat Vorrang
                try:
                    val = cast(ov[cfg_key])
                except Exception:
                    pass
            return val

        return cls(
            hard_tokens_per_run = pick("max_tokens_per_run",  "QATAKI_MAX_TOKENS_PER_RUN",  50_000,  int),
            soft_tokens_per_run = pick("soft_tokens_per_run", "QATAKI_SOFT_TOKENS_PER_RUN", 40_000,  int),
            sparmode_tokens     = pick("sparmode_tokens",     "QATAKI_SPARMODE_TOKENS",     45_000,  int),
            hard_usd_per_run    = pick("max_usd_per_run",     "QATAKI_MAX_USD_PER_RUN",     1.00,    float),
            hard_tokens_per_day = pick("max_tokens_per_day",  "QATAKI_MAX_TOKENS_PER_DAY",  500_000, int),
            hard_usd_per_day    = pick("max_usd_per_day",     "QATAKI_MAX_USD_PER_DAY",     5.00,    float),
            hard_usd_per_month  = pick("max_usd_per_month",   "QATAKI_MAX_USD_PER_MONTH",   50.00,   float),
            confirm_above_usd   = pick("confirm_above_usd",   "QATAKI_CONFIRM_ABOVE_USD",   0.10,    float),
        )

    def to_dict(self) -> dict:
        return {
            "hard_tokens_per_run": self.hard_tokens_per_run,
            "soft_tokens_per_run": self.soft_tokens_per_run,
            "sparmode_tokens":     self.sparmode_tokens,
            "hard_usd_per_run":    self.hard_usd_per_run,
            "hard_tokens_per_day": self.hard_tokens_per_day,
            "hard_usd_per_day":    self.hard_usd_per_day,
            "hard_usd_per_month":  self.hard_usd_per_month,
            "confirm_above_usd":   self.confirm_above_usd,
        }


@dataclass
class CostGuard:
    """Firewall fuer alle LLM-Kosten. Vor JEDEM LLM-Call aufrufen."""
    limits: CostLimits = field(default_factory=CostLimits.from_env)
    _sparmode: bool = field(default=False, init=False)
    _soft_warned: bool = field(default=False, init=False)

    # ── Run-Level-Checks (in-memory) ──────────────────────────────────────

    def check(self, costs: RunCosts) -> list[CostWarning]:
        """Prueft Run-Limits. Warnungen zurueck, CostLimitExceeded bei Hard-Stop."""
        warnings: list[CostWarning] = []

        # NOTAUS -- absoluter Vorrang
        try:
            from qataki.killswitch import is_active
            if is_active():
                raise CostLimitExceeded("NOTAUS aktiv", costs)
        except ImportError:
            pass

        if costs.tokens >= self.limits.hard_tokens_per_run:
            raise CostLimitExceeded(
                f"Hard-Token-Limit: {costs.tokens:,} / {self.limits.hard_tokens_per_run:,}", costs)
        if costs.cost_usd >= self.limits.hard_usd_per_run:
            raise CostLimitExceeded(
                f"Hard-USD-Limit: ${costs.cost_usd:.4f} / ${self.limits.hard_usd_per_run:.2f}", costs)

        if costs.tokens >= self.limits.soft_tokens_per_run and not self._soft_warned:
            self._soft_warned = True
            pct = costs.tokens * 100 // self.limits.hard_tokens_per_run
            warnings.append(CostWarning(f"Naehert sich Token-Limit: {costs.tokens:,} ({pct}%)", "warn"))
        if costs.tokens >= self.limits.sparmode_tokens and not self._sparmode:
            self._sparmode = True
            pct = costs.tokens * 100 // self.limits.hard_tokens_per_run
            warnings.append(CostWarning(f"Sparmode aktiv bei {costs.tokens:,} Tokens ({pct}%)", "sparmode"))
            log.warning("CostGuard: SPARMODE (%d Tokens)", costs.tokens)

        return warnings

    def record_llm_call(self, costs: RunCosts, prompt_tokens: int, completion_tokens: int,
                        cost_usd: float = 0.0, model: str = "default") -> list[CostWarning]:
        """Tokens buchen + sofort pruefen. Berechnet USD wenn nicht uebergeben."""
        from qataki.cost.pricing import calculate_cost
        if cost_usd == 0.0 and (prompt_tokens + completion_tokens) > 0:
            cost_usd = calculate_cost(model, prompt_tokens, completion_tokens)
        costs.add(prompt_tokens, completion_tokens, cost_usd)
        warnings = self.check(costs)
        _audit_log(costs, "llm_call", {
            "model": model, "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens, "cost_usd": cost_usd,
        })
        return warnings

    @property
    def sparmode(self) -> bool:
        return self._sparmode

    def sparmode_suffix(self) -> str:
        if not self._sparmode:
            return ""
        return ("\n\nKOSTEN-SPARMODUS AKTIV: Antworte extrem kurz und praezise. "
                "Kein Fliesstext. Nur das Wesentliche.")

    def sparmode_max_tokens(self, default: int) -> int:
        return 300 if self._sparmode else default

    # ── Tages-/Monats-Checks (aus llm_costs via cost_analytics) ───────────

    def check_budget(self) -> None:
        """Prueft Tages-/Monatsbudget. Wirft CostLimitExceeded bei Ueberschreitung."""
        from qataki.cost import cost_analytics
        day   = cost_analytics.totals("today")
        month = cost_analytics.totals("month")

        if day["total_tokens"] >= self.limits.hard_tokens_per_day:
            raise CostLimitExceeded(
                f"Tages-Token-Limit: {day['total_tokens']:,} / {self.limits.hard_tokens_per_day:,}")
        if day["cost_usd"] >= self.limits.hard_usd_per_day:
            raise CostLimitExceeded(
                f"Tages-USD-Limit: ${day['cost_usd']:.2f} / ${self.limits.hard_usd_per_day:.2f}")
        if month["cost_usd"] >= self.limits.hard_usd_per_month:
            raise CostLimitExceeded(
                f"Monats-USD-Limit: ${month['cost_usd']:.2f} / ${self.limits.hard_usd_per_month:.2f}")

    def budget_status(self) -> dict:
        """Aktueller Budget-Stand fuer UI/API."""
        from qataki.cost import cost_analytics
        day   = cost_analytics.totals("today")
        month = cost_analytics.totals("month")
        return {
            "day": {
                "tokens":       day["total_tokens"],
                "tokens_pct":   min(100, day["total_tokens"] * 100 // max(1, self.limits.hard_tokens_per_day)),
                "usd":          round(day["cost_usd"], 4),
                "usd_pct":      min(100, int(day["cost_usd"] * 100 / max(0.01, self.limits.hard_usd_per_day))),
                "limit_tokens": self.limits.hard_tokens_per_day,
                "limit_usd":    self.limits.hard_usd_per_day,
            },
            "month": {
                "usd":       round(month["cost_usd"], 4),
                "usd_pct":   min(100, int(month["cost_usd"] * 100 / max(0.01, self.limits.hard_usd_per_month))),
                "limit_usd": self.limits.hard_usd_per_month,
            },
            "limits": self.limits.to_dict(),
        }


def _audit_log(costs: RunCosts, event: str, data: dict) -> None:
    try:
        _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _AUDIT_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts":       datetime.now(timezone.utc).isoformat(),
                "event":    event,
                "tokens":   costs.tokens,
                "cost_usd": round(costs.cost_usd, 6),
                **data,
            }, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("cost audit failed: %s", e)
