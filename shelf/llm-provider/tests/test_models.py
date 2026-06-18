"""test_models.py — API v1 Models."""
from uc_llm_provider.core.models import (
    CacheControl,
    CapabilitiesResponse,
    CapabilityTier,
    # Aliases
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatRequest,
    ChatResponse,
    ContentDeltaEvent,
    FinishReason,
    Message,
    MessageDeltaEvent,
    MessageStartEvent,
    MessageStopEvent,
    TextBlock,
    ThinkingBlock,
    ThinkingConfig,
    TokenCountResponse,
    ToolResultBlock,
    ToolUseBlock,
    Usage,
)


def test_text_block():
    b = TextBlock(text="Hello")
    assert b.type == "text"
    assert b.text == "Hello"


def test_text_block_cache_control():
    b = TextBlock(text="Cached", cache_control=CacheControl())
    assert b.cache_control.type == "ephemeral"


def test_tool_use_block():
    b = ToolUseBlock(id="t1", name="search", input={"q": "test"})
    assert b.type == "tool_use"
    assert b.name == "search"


def test_tool_result_block():
    b = ToolResultBlock(tool_use_id="t1", content="result")
    assert b.type == "tool_result"
    assert not b.is_error


def test_thinking_block():
    b = ThinkingBlock(thinking="Let me think...")
    assert b.type == "thinking"


def test_message_string_content():
    m = Message(role="user", content="Hello")
    assert m.content == "Hello"


def test_message_block_content():
    m = Message(role="assistant", content=[TextBlock(text="Hi")])
    assert isinstance(m.content, list)
    assert m.content[0].type == "text"


def test_request_system_text():
    req = ChatRequest(
        model="test",
        messages=[Message(role="user", content="Hi")],
        system="You are helpful.",
    )
    assert req.system_text() == "You are helpful."


def test_request_stop_sequences():
    req = ChatRequest(
        model="test",
        messages=[Message(role="user", content="Hi")],
        stop_sequences=["STOP", "END"],
    )
    assert req.stop_sequences == ["STOP", "END"]


def test_request_extra_passthrough():
    req = ChatRequest(
        model="test",
        messages=[Message(role="user", content="Hi")],
        extra={"top_k": 40, "reasoning_effort": "high"},
        extra_headers={"anthropic-beta": "interleaved-thinking-2025-05-14"},
    )
    assert req.extra["top_k"] == 40
    assert req.extra_headers["anthropic-beta"] == "interleaved-thinking-2025-05-14"


def test_request_thinking():
    req = ChatRequest(
        model="test",
        messages=[Message(role="user", content="Hi")],
        thinking=ThinkingConfig(budget_tokens=2048),
    )
    assert req.thinking.budget_tokens == 2048


def test_usage_total_tokens():
    u = Usage(input_tokens=10, output_tokens=5, thinking_tokens=20)
    assert u.total_tokens == 35


def test_usage_cache_tokens():
    u = Usage(input_tokens=10, output_tokens=5, cache_read_tokens=100, cache_write_tokens=50)
    assert u.cache_read_tokens == 100


def test_response_text_property():
    resp = ChatResponse(
        model="test",
        content=[ThinkingBlock(thinking="..."), TextBlock(text="Hello!")],
        stop_reason=FinishReason.stop,
    )
    assert resp.text == "Hello!"


def test_response_tool_uses():
    resp = ChatResponse(
        model="test",
        content=[
            TextBlock(text="Using tool"),
            ToolUseBlock(id="t1", name="search", input={}),
        ],
        stop_reason=FinishReason.tool_use,
    )
    assert len(resp.tool_uses) == 1
    assert resp.tool_uses[0].name == "search"


def test_response_thinking_property():
    resp = ChatResponse(
        model="test",
        content=[ThinkingBlock(thinking="Deep thought"), TextBlock(text="Answer")],
        stop_reason=FinishReason.stop,
    )
    assert resp.thinking == "Deep thought"


def test_finish_reason_enum():
    assert FinishReason.stop.value       == "stop"
    assert FinishReason.max_tokens.value == "max_tokens"
    assert FinishReason.tool_use.value   == "tool_use"
    assert FinishReason.error.value      == "error"


def test_stream_events():
    start   = MessageStartEvent(model="test", usage=Usage(input_tokens=10))
    delta   = ContentDeltaEvent(index=0, delta=TextBlock(text="Hello"))
    end     = MessageDeltaEvent(stop_reason=FinishReason.stop, usage=Usage(output_tokens=5))
    stop    = MessageStopEvent()
    assert start.type == "message_start"
    assert delta.type == "content_delta"
    assert end.type   == "message_delta"
    assert stop.type  == "message_stop"


def test_token_count_response():
    r = TokenCountResponse(input_tokens=42, model="test", provider="mock")
    assert r.input_tokens == 42


def test_capabilities():
    caps = CapabilitiesResponse(
        provider="mock",
        tiers=CapabilityTier(core=["chat"], extended=[], specialized=[]),
        features={"mock": True},
    )
    assert "chat" in caps.tiers.core


def test_backwards_compat_aliases():
    assert ChatCompletionRequest is ChatRequest
    assert ChatCompletionResponse is ChatResponse
