"""
Test fixtures — MockProvider ohne Netzwerk, API v1.
"""
import pytest

from uc_llm_provider.core.base import BaseProvider
from uc_llm_provider.core.models import (
    ChatRequest,
    ChatResponse,
    ContentDeltaEvent,
    FinishReason,
    Message,
    MessageDeltaEvent,
    MessageStartEvent,
    MessageStopEvent,
    StreamEvent,
    TextBlock,
    TokenCountRequest,
    TokenCountResponse,
    Usage,
)
from uc_llm_provider.logging.cost_logger import CostLogger, reset_cost_logger
from uc_llm_provider.logging.request_logger import RequestResponseLogger


class MockProvider(BaseProvider):
    """Minimale BaseProvider-Implementierung ohne Netzwerk."""

    _tier1_core        = ["chat", "chat_stream", "token_count"]
    _tier2_extended    = []
    _tier3_specialized = []
    _features          = {"mock": True}

    def _get_headers(self) -> dict:
        return {"Content-Type": "application/json"}

    def _get_endpoint(self, path: str = "") -> str:
        return "http://mock.local/v1/chat"

    def _transform_request(self, request: ChatRequest) -> dict:
        return {"model": request.model, "messages": [
            {"role": m.role, "content": m.content if isinstance(m.content, str) else ""}
            for m in request.messages
        ]}

    def _transform_response(self, raw: dict) -> ChatResponse:
        return ChatResponse(
            model=raw.get("model", "mock-model"),
            content=[TextBlock(text=raw.get("content", "mock response"))],
            stop_reason=FinishReason.stop,
            usage=Usage(input_tokens=10, output_tokens=5),
            provider="mock",
        )

    def _transform_stream_request(self, request: ChatRequest) -> dict:
        return {**self._transform_request(request), "stream": True}

    def _parse_stream_event(self, raw_line: str) -> StreamEvent | None:
        return ContentDeltaEvent(index=0, delta=TextBlock(text="chunk"))

    # Override chat() — kein Netzwerk
    async def chat(self, request: ChatRequest) -> ChatResponse:
        return self._transform_response({"model": "mock-model", "content": "mock response"})

    async def chat_stream(self, request: ChatRequest):
        yield MessageStartEvent(model="mock-model")
        yield ContentDeltaEvent(index=0, delta=TextBlock(text="mock "))
        yield ContentDeltaEvent(index=0, delta=TextBlock(text="response"))
        yield MessageDeltaEvent(stop_reason=FinishReason.stop)
        yield MessageStopEvent()

    async def count_tokens(self, request: TokenCountRequest) -> TokenCountResponse:
        text = " ".join(
            m.content for m in request.messages if isinstance(m.content, str)
        )
        return TokenCountResponse(
            input_tokens=len(text.split()),
            model=request.model or "mock-model",
            provider="mock",
        )


@pytest.fixture(autouse=True)
def reset_logger():
    reset_cost_logger()
    yield
    reset_cost_logger()


@pytest.fixture
def mock_provider():
    return MockProvider({"name": "mock", "provider_type": "mock", "default_model": "mock-model"})


@pytest.fixture
def no_log_provider():
    logger   = RequestResponseLogger("test", enabled=False)
    cost_log = CostLogger(enabled=False)
    return MockProvider(
        {"name": "mock", "provider_type": "mock", "default_model": "mock-model"},
        logger=logger,
        cost_logger=cost_log,
    )


@pytest.fixture
def basic_request():
    return ChatRequest(
        model="mock-model",
        messages=[Message(role="user", content="Hello")],
        max_tokens=100,
    )
