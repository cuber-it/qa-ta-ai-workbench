"""
Factory — get_provider() und register_provider().
Einziger Ort wo Provider-Klassen bekannt sind.
"""
from .core.base import BaseProvider
from .providers import (
    AnthropicProvider,
    GoogleProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
)

_REGISTRY: dict[str, type[BaseProvider]] = {
    "anthropic":         AnthropicProvider,
    "openai":            OpenAIProvider,
    "google":            GoogleProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "ollama":            OllamaProvider,
    "lm_studio":         OpenAICompatibleProvider,
    "lmstudio":          OpenAICompatibleProvider,
    "llamacpp":          OpenAICompatibleProvider,
    "vllm":              OpenAICompatibleProvider,
    "localai":           OpenAICompatibleProvider,
}


def get_provider(config: dict) -> BaseProvider:
    """
    Erstellt den richtigen Provider aus einer Config-Dict.
    config muss enthalten: provider_type, name
    """
    pt = config.get("provider_type", "").lower()
    if not pt:
        raise ValueError(
            f"config muss 'provider_type' enthalten. Verfügbar: {sorted(_REGISTRY)}"
        )
    cls = _REGISTRY.get(pt)
    if cls is None:
        raise ValueError(
            f"Unbekannter provider_type: '{pt}'. Verfügbar: {sorted(_REGISTRY)}"
        )
    return cls(config)


def register_provider(provider_type: str, cls: type[BaseProvider]) -> None:
    """Registriert einen eigenen Provider-Typ."""
    _REGISTRY[provider_type.lower()] = cls
