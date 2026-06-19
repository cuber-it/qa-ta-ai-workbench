"""
PricingSubagent — haelt Tarife aktuell.

Laeuft taeglich ~08:00 oder auf manuelle Anfrage. Laedt die Pricing-Seiten
der Provider per Playwright, extrahiert die Preise per LLM, schreibt einen
Diff -> User bestaetigt in den Einstellungen. Ueberspringt freie/lokale
Provider.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

log = logging.getLogger(__name__)

PRICING_SOURCES = {
    "openai": {
        "url":  "https://openai.com/api/pricing/",
        "hint": "Find a table with model names and prices per million tokens. "
                "Look for input and output token prices.",
    },
    "anthropic": {
        "url":  "https://www.anthropic.com/pricing",
        "hint": "Find Claude model pricing table with input and output costs per million tokens.",
    },
    "google": {
        "url":  "https://ai.google.dev/pricing",
        "hint": "Find Gemini model pricing with input and output costs per million tokens.",
    },
}

EXTRACT_PROMPT = """
Extract LLM model pricing from this page content.

{hint}

Return a JSON array. Each item:
{{
  "model": "exact-model-name-as-used-in-api",
  "prompt_per_mtok": <float, USD per 1M input tokens>,
  "completion_per_mtok": <float, USD per 1M output tokens>
}}

Rules:
- Use the API model identifier (e.g. "gpt-4o-mini", not "GPT-4o Mini")
- Prices in USD per 1,000,000 tokens
- Skip embedding models, image models, audio models
- Skip if price unclear or not found
- Return ONLY the JSON array, nothing else

Page content:
{content}
"""


class PricingSubagent:

    def __init__(self, provider=None):
        # provider: uc-llm-provider Instanz fuer die Extraktion. None -> aus Settings bauen.
        self._provider = provider

    async def run(self, providers: list[str] | None = None) -> dict:
        from qataki import settings_store
        from uc_llm_cost.pricing_store import is_free_provider, set_pending_diff

        s = settings_store.load()
        if is_free_provider(s.get("provider_type", "")):
            log.info("PricingSubagent: skip (freier Provider: %s)", s.get("provider_type"))
            return {"checked": [], "changes": [], "errors": [], "skipped": "free provider"}

        to_check = providers or list(PRICING_SOURCES.keys())
        checked: list[str] = []
        all_changes: list[dict] = []
        errors: list[str] = []

        for provider_name in to_check:
            source = PRICING_SOURCES.get(provider_name)
            if not source:
                continue
            try:
                log.info("PricingSubagent: checking %s", provider_name)
                content = await self._fetch_page(source["url"])
                if not content:
                    errors.append(f"{provider_name}: page fetch failed")
                    continue
                extracted = await self._extract_prices(content[:8000], source["hint"], provider_name)
                changes = self._diff(extracted)
                all_changes.extend(changes)
                checked.append(provider_name)
                log.info("PricingSubagent: %s -> %d changes", provider_name, len(changes))
            except Exception as e:
                log.warning("PricingSubagent: %s failed: %s", provider_name, e)
                errors.append(f"{provider_name}: {e}")

        if all_changes:
            set_pending_diff(all_changes)
            log.info("PricingSubagent: %d changes pending confirmation", len(all_changes))

        return {
            "checked":    checked,
            "changes":    all_changes,
            "errors":     errors,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _fetch_page(self, url: str) -> str | None:
        """Laedt Seite via Playwright. 'load' + kurze Pause, damit JS-SPAs rendern."""
        try:
            from uc_playwright_driver import tools
            from uc_playwright_driver.client import BrowserClient

            client = BrowserClient({"headless": True, "timeout": 25000})
            try:
                await tools.navigate(client, url, wait_until="load")
                await asyncio.sleep(2.5)
                content = await tools.get_page_content(client, max_length=12000)
            finally:
                await client.cleanup()
            return content or None
        except Exception as e:
            log.warning("PricingSubagent._fetch_page failed: %s", e)
            return None

    async def _extract_prices(self, content: str, hint: str, provider_name: str) -> list[dict]:
        """Nutzt das konfigurierte LLM, um Preise aus dem Page-Content zu ziehen."""
        from qataki import llm, settings_store
        from uc_llm_provider import ChatMessage, ChatRequest

        if self._provider is None:
            try:
                self._provider = llm._provider(settings_store.load())
            except Exception as e:
                log.warning("PricingSubagent: provider build failed: %s", e)
                return []

        s = settings_store.load()
        model = s.get("model") or self._provider.get_default_model()
        req = ChatRequest(
            model=model,
            messages=[ChatMessage(role="user", content=EXTRACT_PROMPT.format(hint=hint, content=content))],
            max_tokens=2000,
        )
        resp = await self._provider.chat(req)
        raw = llm._text(resp).strip()

        try:
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            if not m:
                return []
            items = json.loads(m.group(0))
            result = []
            for item in items:
                if isinstance(item, dict) and "model" in item:
                    result.append({
                        "model":               item["model"],
                        "prompt_per_mtok":     float(item.get("prompt_per_mtok", 0)),
                        "completion_per_mtok": float(item.get("completion_per_mtok", 0)),
                        "provider":            provider_name,
                    })
            return result
        except Exception as e:
            log.warning("PricingSubagent._extract_prices parse error: %s", e)
            return []

    def _diff(self, extracted: list[dict]) -> list[dict]:
        """Vergleicht extrahierte Preise mit den aktuellen Tarifen (>5% = Aenderung)."""
        from uc_llm_cost.pricing_store import get_rates
        changes = []
        for item in extracted:
            model = item["model"]
            new_p = item["prompt_per_mtok"]
            new_c = item["completion_per_mtok"]
            cur_p, cur_c = get_rates(model)
            changed = (
                abs(new_p - cur_p) > cur_p * 0.05
                or abs(new_c - cur_c) > cur_c * 0.05
                or (cur_p == 1.0 and cur_c == 3.0)   # war "default"-Schaetzung
            )
            if changed and (new_p > 0 or new_c > 0):
                changes.append({
                    "model":          model,
                    "provider":       item.get("provider", "?"),
                    "old_prompt":     cur_p,
                    "old_completion": cur_c,
                    "new_prompt":     new_p,
                    "new_completion": new_c,
                })
        return changes


# ── Scheduler ────────────────────────────────────────────────────────────────

_last_run: datetime | None = None


async def maybe_run_daily() -> None:
    """Taeglich ~08:00 -- aufgerufen aus dem App-Lifespan (optional)."""
    global _last_run
    now = datetime.now(timezone.utc)
    if _last_run and (now - _last_run).total_seconds() < 3600 * 20:
        return
    if now.hour != 8:
        return
    _last_run = now
    log.info("PricingSubagent: daily run starting")
    await PricingSubagent().run()
