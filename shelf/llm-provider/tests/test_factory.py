"""test_factory.py — get_provider() für alle types, Fehlerfall."""
import pytest

from uc_llm_provider import get_provider, register_provider
from uc_llm_provider.providers import (
    AnthropicProvider,
    GoogleProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
)


@pytest.mark.parametrize("pt,expected_cls", [
    ("anthropic",        AnthropicProvider),
    ("openai",           OpenAIProvider),
    ("google",           GoogleProvider),
    ("ollama",           OllamaProvider),
    ("openai_compatible",OpenAICompatibleProvider),
    ("lm_studio",        OpenAICompatibleProvider),
    ("vllm",             OpenAICompatibleProvider),
    ("llamacpp",         OpenAICompatibleProvider),
    ("localai",          OpenAICompatibleProvider),
])
def test_get_provider_all_types(pt, expected_cls):
    p = get_provider({
        "name": pt, "provider_type": pt,
        "default_model": "test", "api_base": "http://localhost",
    })
    assert isinstance(p, expected_cls)


def test_get_provider_missing_type():
    with pytest.raises(ValueError, match="provider_type"):
        get_provider({"name": "x"})


def test_get_provider_unknown_type():
    with pytest.raises(ValueError, match="Unbekannter"):
        get_provider({"name": "x", "provider_type": "does_not_exist"})


def test_register_provider():
    from tests.conftest import MockProvider
    register_provider("test_mock", MockProvider)
    p = get_provider({"name": "test_mock", "provider_type": "test_mock", "default_model": "m"})
    assert isinstance(p, MockProvider)


def test_provider_default_model():
    p = get_provider({"name": "openai", "provider_type": "openai", "default_model": "gpt-custom"})
    assert p.get_default_model() == "gpt-custom"
