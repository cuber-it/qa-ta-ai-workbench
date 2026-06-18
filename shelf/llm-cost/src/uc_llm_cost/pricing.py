"""
Token-Pricing — Tarife aller unterstützten Modelle.

Preise in USD per 1.000.000 Token (= per MTok).
Quelle: Offizielle Preisseiten der Provider.

WICHTIG: Preise ändern sich! pricing_agent hält sie aktuell,
Bestätigung in den Einstellungen. Stand der Defaults: 2026-05-20.
"""
from __future__ import annotations

# Preise in USD per 1.000.000 Token
# Format: "model_name": (prompt_per_mtok, completion_per_mtok)
PRICING: dict[str, tuple[float, float]] = {

    # ── OpenAI ────────────────────────────────────────────────────────────
    "gpt-4o":                  (2.50,  10.00),
    "gpt-4o-2024-11-20":       (2.50,  10.00),
    "gpt-4o-mini":             (0.15,   0.60),
    "gpt-4o-mini-2024-07-18":  (0.15,   0.60),
    "gpt-4-turbo":             (10.00,  30.00),
    "gpt-4":                   (30.00,  60.00),
    "gpt-3.5-turbo":           (0.50,   1.50),
    "o1":                      (15.00,  60.00),
    "o1-mini":                 (1.10,   4.40),
    "o3-mini":                 (1.10,   4.40),

    # ── Anthropic ─────────────────────────────────────────────────────────
    "claude-opus-4-5":                  (15.00,  75.00),
    "claude-sonnet-4-5":                (3.00,   15.00),
    "claude-sonnet-4-20250514":         (3.00,   15.00),
    "claude-haiku-4-5-20251001":        (0.80,    4.00),
    "claude-3-5-sonnet-20241022":       (3.00,   15.00),
    "claude-3-5-haiku-20241022":        (0.80,    4.00),
    "claude-3-opus-20240229":           (15.00,  75.00),
    "claude-3-sonnet-20240229":         (3.00,   15.00),
    "claude-3-haiku-20240307":          (0.25,    1.25),

    # ── Google ────────────────────────────────────────────────────────────
    "gemini-1.5-pro":          (1.25,   5.00),
    "gemini-1.5-flash":        (0.075,  0.30),
    "gemini-1.5-flash-8b":     (0.0375, 0.15),
    "gemini-2.0-flash":        (0.10,   0.40),
    "gemini-2.0-flash-lite":   (0.075,  0.30),

    # ── Ollama (lokal = kostenlos) ─────────────────────────────────────────
    "llama3.2":                (0.0,    0.0),
    "llama3.1":                (0.0,    0.0),
    "mistral":                 (0.0,    0.0),
    "mixtral":                 (0.0,    0.0),
    "phi3":                    (0.0,    0.0),
    "qwen2.5":                 (0.0,    0.0),

    # ── Fallback ──────────────────────────────────────────────────────────
    "scan-llm-v1":             (0.0,    0.0),
    "default":                 (1.00,   3.00),   # konservative Schätzung
}


def calculate_cost(
    model:             str,
    prompt_tokens:     int,
    completion_tokens: int,
) -> float:
    """Berechnet Kosten in USD. Nutzt pricing_store wenn verfügbar."""
    try:
        from .pricing_store import calculate_cost as store_calc
        return store_calc(model, prompt_tokens, completion_tokens)
    except Exception:
        pass
    # Fallback auf lokale PRICING-Tabelle
    rates = PRICING.get(model)
    if not rates:
        for key, val in PRICING.items():
            if model.startswith(key) or key.startswith(model.split("-")[0]):
                rates = val
                break
    if not rates:
        rates = PRICING["default"]
    prompt_cost     = (prompt_tokens     / 1_000_000) * rates[0]
    completion_cost = (completion_tokens / 1_000_000) * rates[1]
    return prompt_cost + completion_cost


def get_rates(model: str) -> tuple[float, float]:
    """Gibt (prompt_per_mtok, completion_per_mtok) zurück."""
    rates = PRICING.get(model)
    if not rates:
        for key, val in PRICING.items():
            if model.startswith(key):
                return val
    return rates or PRICING["default"]


def list_models() -> dict:
    """Alle bekannten Modelle mit Preisen."""
    return {
        model: {
            "prompt_per_mtok":     rates[0],
            "completion_per_mtok": rates[1],
            "local":               rates[0] == 0.0,
        }
        for model, rates in PRICING.items()
        if model != "default"
    }
