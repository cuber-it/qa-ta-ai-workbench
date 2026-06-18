"""
uc-llm-provider — Unified API v1 Models

Das Beste aus Anthropic und OpenAI, bereinigt und ergänzt.

Designprinzipien:
- Typed Content Blocks (Anthropic-inspiriert)
- system als First-Class-Feld
- Anthropic-Naming: input_tokens/output_tokens
- Typisiertes Streaming mit Events
- FinishReason als Enum
- Erweitertes Usage (thinking, cache)
- RequestContext ist intern — wird NIE an Provider gesendet
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class RequestContext(BaseModel):
    """Interner Kontext — wird nicht an Provider gesendet."""
    caller_id:  Optional[str] = None
    session_id: Optional[str] = None
    task_id:    Optional[str] = None



class CacheControl(BaseModel):
    type: Literal["ephemeral"] = "ephemeral"



class ImageSourceBase64(BaseModel):
    type:       Literal["base64"] = "base64"
    media_type: str               # "image/jpeg" | "image/png" | "image/webp" | "image/gif"
    data:       str               # base64-encoded


class ImageSourceURL(BaseModel):
    type: Literal["url"] = "url"
    url:  str


ImageSource = Annotated[Union[ImageSourceBase64, ImageSourceURL], Field(discriminator="type")]


class DocumentSource(BaseModel):
    type:       Literal["base64"] = "base64"
    media_type: Literal["application/pdf"] = "application/pdf"
    data:       str



class TextBlock(BaseModel):
    type:          Literal["text"] = "text"
    text:          str
    cache_control: Optional[CacheControl] = None


class ImageBlock(BaseModel):
    type:   Literal["image"] = "image"
    source: ImageSource


class DocumentBlock(BaseModel):
    type:          Literal["document"] = "document"
    source:        DocumentSource
    cache_control: Optional[CacheControl] = None


class ToolUseBlock(BaseModel):
    type:  Literal["tool_use"] = "tool_use"
    id:    str
    name:  str
    input: dict = Field(default_factory=dict)


class ToolResultBlock(BaseModel):
    type:        Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content:     Union[str, list["ContentBlock"]] = ""
    is_error:    bool = False


class ThinkingBlock(BaseModel):
    type:     Literal["thinking"] = "thinking"
    thinking: str


ContentBlock = Annotated[
    Union[TextBlock, ImageBlock, DocumentBlock, ToolUseBlock, ToolResultBlock, ThinkingBlock],
    Field(discriminator="type"),
]

# Selbstreferenz auflösen
ToolResultBlock.model_rebuild()



class ToolDefinition(BaseModel):
    name:          str
    description:   Optional[str]  = None
    input_schema:  dict            = Field(default_factory=dict)
    cache_control: Optional[CacheControl] = None


class ToolChoiceAuto(BaseModel):
    type: Literal["auto"] = "auto"


class ToolChoiceAny(BaseModel):
    type: Literal["any"] = "any"


class ToolChoiceSpecific(BaseModel):
    type: Literal["tool"] = "tool"
    name: str


ToolChoice = Union[ToolChoiceAuto, ToolChoiceAny, ToolChoiceSpecific]



class ThinkingConfig(BaseModel):
    type:         Literal["enabled"] = "enabled"
    budget_tokens: int = 1024



class Message(BaseModel):
    """
    User oder Assistant Message.
    System ist kein role — es ist ein First-Class-Feld in ChatRequest.
    """
    role:    Literal["user", "assistant"]
    content: Union[str, list[ContentBlock]]



class ChatRequest(BaseModel):
    model:           str
    messages:        list[Message]
    system:          Optional[Union[str, list[TextBlock]]] = None
    max_tokens:      int                                   = 1024
    temperature:     Optional[float]                       = None
    top_p:           Optional[float]                       = None
    stop_sequences:  Optional[list[str]]                   = None
    stream:          bool                                  = False
    tools:           Optional[list[ToolDefinition]]        = None
    tool_choice:     Optional[ToolChoice]                  = None
    thinking:        Optional[ThinkingConfig]              = None
    metadata:        Optional[dict]                        = None
    # Provider-spezifische Pass-throughs — nicht von Providern übersetzt
    extra:           Optional[dict]                        = None
    extra_headers:   Optional[dict]                        = None
    # Intern — wird NIE an Provider gesendet
    context:         Optional[RequestContext]              = None

    def user_messages(self) -> list[Message]:
        """Messages ohne system — für Providers die system separat erwarten."""
        return self.messages

    def system_text(self) -> Optional[str]:
        """System als plain text."""
        if self.system is None:
            return None
        if isinstance(self.system, str):
            return self.system
        return "\n".join(b.text for b in self.system if isinstance(b, TextBlock))



class Usage(BaseModel):
    input_tokens:       int = 0
    output_tokens:      int = 0
    thinking_tokens:    int = 0
    cache_read_tokens:  int = 0
    cache_write_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.thinking_tokens



class FinishReason(str, Enum):
    stop       = "stop"
    max_tokens = "max_tokens"
    tool_use   = "tool_use"
    error      = "error"



class ChatResponse(BaseModel):
    id:          str          = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}")
    model:       str
    content:     list[ContentBlock]
    stop_reason: FinishReason = FinishReason.stop
    usage:       Usage        = Field(default_factory=Usage)
    provider:    Optional[str] = None

    @property
    def text(self) -> str:
        """Alle TextBlocks zusammengeführt."""
        return "".join(b.text for b in self.content if isinstance(b, TextBlock))

    @property
    def tool_uses(self) -> list[ToolUseBlock]:
        """Alle ToolUse-Blocks."""
        return [b for b in self.content if isinstance(b, ToolUseBlock)]

    @property
    def thinking(self) -> Optional[str]:
        """Thinking-Inhalt falls vorhanden."""
        blocks = [b for b in self.content if isinstance(b, ThinkingBlock)]
        return blocks[0].thinking if blocks else None



class MessageStartEvent(BaseModel):
    type:  Literal["message_start"] = "message_start"
    id:    str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}")
    model: str = ""
    usage: Optional[Usage] = None


class ContentDeltaEvent(BaseModel):
    type:  Literal["content_delta"] = "content_delta"
    index: int = 0
    delta: Union[TextBlock, ThinkingBlock]


class ContentStopEvent(BaseModel):
    type:  Literal["content_stop"] = "content_stop"
    index: int = 0


class MessageDeltaEvent(BaseModel):
    type:        Literal["message_delta"] = "message_delta"
    stop_reason: Optional[FinishReason]  = None
    usage:       Optional[Usage]         = None


class MessageStopEvent(BaseModel):
    type: Literal["message_stop"] = "message_stop"


class ErrorEvent(BaseModel):
    type:    Literal["error"] = "error"
    message: str


StreamEvent = Annotated[
    Union[
        MessageStartEvent,
        ContentDeltaEvent,
        ContentStopEvent,
        MessageDeltaEvent,
        MessageStopEvent,
        ErrorEvent,
    ],
    Field(discriminator="type"),
]


# Backwards-Compat Aliases (deprecated, werden in v1.0 entfernt)

# v0.4 Namen
ChatCompletionRequest  = ChatRequest
ChatCompletionResponse = ChatResponse



class EmbeddingRequest(BaseModel):
    input:           Union[str, list[str]]
    model:           Optional[str] = None
    encoding_format: Optional[str] = None
    dimensions:      Optional[int] = None


class EmbeddingData(BaseModel):
    index:     int
    embedding: list[float]


class EmbeddingResponse(BaseModel):
    data:     list[EmbeddingData]
    model:    str
    usage:    dict
    provider: str


class BatchRequestItem(BaseModel):
    custom_id: str
    params:    dict


class BatchCreateRequest(BaseModel):
    requests: list[BatchRequestItem]
    model:    Optional[str] = None


class BatchStatus(BaseModel):
    id:                  str
    status:              str
    total_requests:      Optional[int] = None
    completed_requests:  Optional[int] = None
    failed_requests:     Optional[int] = None
    created_at:          Optional[str] = None
    ended_at:            Optional[str] = None
    provider:            str


class BatchListResponse(BaseModel):
    batches:  list[BatchStatus]
    provider: str


class BatchResultItem(BaseModel):
    custom_id: str
    result:    Optional[Any] = None
    error:     Optional[Any] = None


class BatchResultsResponse(BaseModel):
    batch_id: str
    results:  list[BatchResultItem]
    provider: str


class TokenCountRequest(BaseModel):
    messages: list[Message]
    model:    Optional[str]              = None
    system:   Optional[str]              = None
    tools:    Optional[list[ToolDefinition]] = None


class TokenCountResponse(BaseModel):
    input_tokens: int
    model:        str
    provider:     str


class ModerationRequest(BaseModel):
    input: Union[str, list[str]]
    model: Optional[str] = None


class ModerationResult(BaseModel):
    flagged:         bool
    categories:      dict
    category_scores: dict


class ModerationResponse(BaseModel):
    id:       str
    results:  list[ModerationResult]
    model:    str
    provider: str


class AudioSpeechRequest(BaseModel):
    input:           str
    voice:           str           = "alloy"
    model:           Optional[str]   = None
    response_format: Optional[str]   = None
    speed:           Optional[float] = None


class AudioResponse(BaseModel):
    text:     str
    model:    str
    provider: str


class ImageGenerationRequest(BaseModel):
    prompt:          str
    model:           Optional[str] = None
    n:               int           = 1
    size:            Optional[str] = None
    quality:         Optional[str] = None
    style:           Optional[str] = None
    response_format: Optional[str] = None


class ImageEditRequest(BaseModel):
    prompt: str
    model:  Optional[str] = None
    n:      int           = 1
    size:   Optional[str] = None


class ImageVariationRequest(BaseModel):
    model: Optional[str] = None
    n:     int           = 1
    size:  Optional[str] = None


class ImageData(BaseModel):
    url:            Optional[str] = None
    b64_json:       Optional[str] = None
    revised_prompt: Optional[str] = None


class ImageResponse(BaseModel):
    data:     list[ImageData]
    model:    str
    provider: str


class CapabilityTier(BaseModel):
    core:        list[str]
    extended:    list[str]
    specialized: list[str]


class CapabilitiesResponse(BaseModel):
    provider: str
    tiers:    CapabilityTier
    features: dict


class HealthResponse(BaseModel):
    status:    str
    provider:  str
    timestamp: str


class ModelDetail(BaseModel):
    id:        str
    name:      str
    provider:  str
    owned_by:  Optional[str] = None
    created:   Optional[str] = None


class NotImplementedResponse(BaseModel):
    endpoint: str
    provider: str
    message:  str


class ConnectionStatus(BaseModel):
    status:    str
    provider:  str
    timestamp: str
    reset:     bool = False
