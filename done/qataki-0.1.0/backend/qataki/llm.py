"""LLM-Anbindung ueber uc-llm-provider, inkl. Kosten-Summary."""
import os

from uc_llm_provider import ChatMessage, ChatRequest, get_provider
from uc_llm_provider.logging import get_cost_logger

from . import cancellation

KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


def key_present(provider_type: str) -> bool:
    return bool(os.getenv(KEY_ENV.get(provider_type, ""), ""))


def _provider(settings: dict):
    cfg = {"provider_type": settings["provider_type"], "name": settings["provider_type"]}
    return get_provider(cfg)


def _text(resp) -> str:
    c = resp.content
    if isinstance(c, str):
        return c
    parts = []
    for b in c or []:
        t = getattr(b, "text", None)
        if t is None and isinstance(b, dict):
            t = b.get("text")
        if t:
            parts.append(t)
    return "".join(parts)


async def chat(settings: dict, messages: list[dict], system: str | None = None) -> dict:
    prov = _provider(settings)
    req = ChatRequest(
        model=settings.get("model") or None,
        messages=[ChatMessage(role=m["role"], content=m["content"]) for m in messages],
        system=system,
        max_tokens=int(settings.get("max_tokens", 1024)),
        temperature=float(settings.get("temperature", 0.7)),
    )
    resp = await cancellation.run(prov.chat(req))
    u = resp.usage
    usage = {
        "input_tokens": getattr(u, "input_tokens", 0),
        "output_tokens": getattr(u, "output_tokens", 0),
    } if u else {}
    return {"text": _text(resp), "model": resp.model, "usage": usage}


def cost_summary() -> dict:
    return get_cost_logger().summary()
