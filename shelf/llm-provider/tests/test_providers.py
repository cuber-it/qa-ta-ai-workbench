"""test_providers.py — Provider instanziieren, capabilities, transform."""
import pytest

from uc_llm_provider import get_provider
from uc_llm_provider.core.models import (
    ChatRequest,
    Message,
    TokenCountRequest,
)


def _provider(pt, **kw):
    return get_provider({
        "name": pt, "provider_type": pt,
        "default_model": "test-model",
        "api_base": "http://localhost",
        "api_key": "test-key",
        **kw,
    })


@pytest.mark.parametrize("pt", ["anthropic", "openai", "google", "ollama", "openai_compatible"])
def test_get_capabilities(pt):
    p    = _provider(pt)
    caps = p.get_capabilities()
    assert caps.provider == pt
    assert len(caps.tiers.core) > 0


@pytest.mark.parametrize("pt", ["anthropic", "openai", "ollama"])
def test_transform_request(pt):
    p   = _provider(pt)
    req = ChatRequest(
        model="test-model",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
        system="Be helpful.",
    )
    payload = p._transform_request(req)
    assert "messages" in payload or "contents" in payload


@pytest.mark.parametrize("pt", ["anthropic", "openai", "ollama"])
def test_headers(pt):
    headers = _provider(pt, api_key="test-key")._get_headers()
    assert isinstance(headers, dict)
    assert "Content-Type" in headers


@pytest.mark.parametrize("pt", ["anthropic", "openai", "ollama", "openai_compatible"])
def test_endpoint(pt):
    assert _provider(pt)._get_endpoint().startswith("http")


def test_mock_capabilities(mock_provider):
    caps = mock_provider.get_capabilities()
    assert "chat" in caps.tiers.core
    assert caps.features.get("mock") is True


def test_mock_transform(mock_provider, basic_request):
    payload = mock_provider._transform_request(basic_request)
    assert payload["model"] == "mock-model"
    assert payload["messages"][0]["content"] == "Hello"


@pytest.mark.asyncio
async def test_mock_chat(mock_provider, basic_request):
    resp = await mock_provider.chat(basic_request)
    assert resp.text == "mock response"
    assert resp.stop_reason.value == "stop"


@pytest.mark.asyncio
async def test_mock_stream(mock_provider, basic_request):
    events = []
    async for ev in mock_provider.chat_stream(basic_request):
        events.append(ev.type)
    assert "message_start" in events
    assert "content_delta" in events
    assert "message_stop" in events


@pytest.mark.asyncio
async def test_mock_count_tokens(mock_provider):
    req    = TokenCountRequest(
        messages=[Message(role="user", content="Hello world test")],
        model="mock",
    )
    result = await mock_provider.count_tokens(req)
    assert result.input_tokens == 3


def test_anthropic_system_in_payload():
    p   = _provider("anthropic")
    req = ChatRequest(
        model="claude-sonnet-4-20250514",
        messages=[Message(role="user", content="Hi")],
        system="You are helpful.",
        max_tokens=100,
    )
    payload = p._transform_request(req)
    assert payload.get("system") == "You are helpful."
    # system darf nicht in messages sein
    assert not any(m.get("role") == "system" for m in payload["messages"])


def test_openai_system_in_messages():
    p   = _provider("openai")
    req = ChatRequest(
        model="gpt-4o-mini",
        messages=[Message(role="user", content="Hi")],
        system="Be helpful.",
        max_tokens=100,
    )
    payload = p._transform_request(req)
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][0]["content"] == "Be helpful."
