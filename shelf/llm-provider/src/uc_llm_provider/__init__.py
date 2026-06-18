"""
uc-llm-provider — Unified API v1

Library usage:
    from uc_llm_provider import get_provider, ChatRequest, Message
    provider = get_provider({"provider_type": "anthropic", "api_key": "..."})
    response = await provider.chat(ChatRequest(model="...", messages=[...]))
"""
from .core.models import (
    # Backwards-compat
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatRequest,
    ChatResponse,
    FinishReason,
    Message,
    RequestContext,
    StreamEvent,
    TextBlock,
    ToolDefinition,
    ToolUseBlock,
    Usage,
)
from .factory import get_provider, register_provider

__version__ = "0.5.1"

# Legacy aliases
ChatMessage = Message

__all__ = [
    "get_provider",
    "register_provider",
    # API v1
    "ChatRequest",
    "ChatResponse",
    "Message",
    "TextBlock",
    "ToolDefinition",
    "ToolUseBlock",
    "Usage",
    "FinishReason",
    "StreamEvent",
    "RequestContext",
    # backwards compat
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "ChatMessage",
]
