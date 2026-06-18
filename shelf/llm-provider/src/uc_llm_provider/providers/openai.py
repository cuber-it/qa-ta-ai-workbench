"""
uc-llm-provider — OpenAI Provider
Unified → OpenAI-API-Format → Unified

Übersetzungen:
- system TextBlock → messages[0] role=system
- ContentBlocks → OpenAI content array
- ToolUseBlock → tool_calls
- ToolResultBlock → role=tool message
- stop_sequences → stop
- thinking → reasoning_effort (o-series)
- input_tokens/output_tokens ← prompt_tokens/completion_tokens
"""
import json
import os

from ..core.base import BaseProvider
from ..core.models import (
    ChatRequest,
    ChatResponse,
    ContentDeltaEvent,
    FinishReason,
    MessageDeltaEvent,
    MessageStartEvent,
    ModelDetail,
    StreamEvent,
    TextBlock,
    TokenCountRequest,
    TokenCountResponse,
    ToolUseBlock,
    Usage,
)
from ._openai_tier2 import OpenAITier2Mixin
from ._openai_tier3 import OpenAITier3Mixin
from ._openai_tools import (
    is_block,
    translate_assistant_tool_msg,
    translate_tool_result_msgs,
)

_FINISH_REASON_MAP = {
    "stop":        FinishReason.stop,
    "length":      FinishReason.max_tokens,
    "tool_calls":  FinishReason.tool_use,
    "content_filter": FinishReason.stop,
}


class OpenAIProvider(OpenAITier2Mixin, OpenAITier3Mixin, BaseProvider):

    _tier1_core = ["chat", "chat_stream", "models_list", "model_detail", "token_count"]
    _tier2_extended = ["embeddings", "batches"]
    _tier3_specialized = [
        "moderation", "audio_transcription", "audio_translation",
        "audio_speech", "image_generation", "image_edit", "image_variation",
    ]
    _features = {
        "tool_use": True, "vision": True, "web_search": False,
        "citations": False, "thinking": True, "cache_control": False,
        "embeddings": True, "audio": True, "images": True, "moderation": True,
        "top_k": False, "stop_sequences": True,
    }

    _NEW_TOKEN_MODELS = {"gpt-5", "o3", "o4", "o1"}

    def _get_headers(self) -> dict:
        key = self.config.get("api_key") or os.getenv("OPENAI_API_KEY", "")
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _get_endpoint(self, path: str = "/chat/completions") -> str:
        base = self.config.get("api_base", "https://api.openai.com/v1")
        return f"{base}{path}"


    def _transform_request(self, request: ChatRequest) -> dict:
        model = request.model or self.get_default_model()
        msgs  = []

        # system → messages[0]
        sys_text = request.system_text()
        if sys_text:
            msgs.append({"role": "system", "content": sys_text})

        for m in request.messages:
            if m.role == "assistant" and isinstance(m.content, list) and \
               any(is_block(b, "tool_use") for b in m.content):
                msgs.append(translate_assistant_tool_msg(m.content))
            elif m.role == "user" and isinstance(m.content, list) and \
                 any(is_block(b, "tool_result") for b in m.content):
                msgs.extend(translate_tool_result_msgs(m.content))
            else:
                msgs.append({"role": m.role, "content": self._to_openai_content(m.content)})

        token_key = (
            "max_completion_tokens"
            if any(m in model for m in self._NEW_TOKEN_MODELS)
            else "max_tokens"
        )
        payload: dict = {"model": model, token_key: request.max_tokens, "messages": msgs}

        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.stop_sequences:
            payload["stop"] = request.stop_sequences
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name":        t.name,
                        "description": t.description or "",
                        "parameters":  t.input_schema,
                    },
                }
                for t in request.tools
            ]
        if request.tool_choice:
            tc = request.tool_choice
            if hasattr(tc, "type"):
                if tc.type == "tool":
                    payload["tool_choice"] = {"type": "function", "function": {"name": tc.name}}
                else:
                    payload["tool_choice"] = tc.type
        if request.thinking:
            payload["reasoning_effort"] = "high"
        if request.metadata:
            payload["metadata"] = request.metadata
        return payload

    def _to_openai_content(self, content) -> str | list:
        if isinstance(content, str):
            return content
        result = []
        for block in content:
            t = block.type if hasattr(block, "type") else block.get("type")
            if t == "text":
                result.append({"type": "text", "text": block.text})
            elif t == "image":
                src = block.source
                if src.type == "base64":
                    url = f"data:{src.media_type};base64,{src.data}"
                else:
                    url = src.url
                result.append({"type": "image_url", "image_url": {"url": url}})
        if len(result) == 1 and result[0]["type"] == "text":
            return result[0]["text"]
        return result


    def _transform_response(self, raw: dict) -> ChatResponse:
        ch  = raw["choices"][0]
        msg = ch["message"]

        content_blocks = []
        if msg.get("content"):
            content_blocks.append(TextBlock(text=msg["content"]))
        for tc in msg.get("tool_calls") or []:
            content_blocks.append(ToolUseBlock(
                id=tc["id"],
                name=tc["function"]["name"],
                input=json.loads(tc["function"].get("arguments", "{}")),
            ))

        finish = ch.get("finish_reason", "stop")
        u      = raw.get("usage", {})

        return ChatResponse(
            id=raw.get("id", ""),
            model=raw.get("model", self.get_default_model()),
            content=content_blocks,
            stop_reason=_FINISH_REASON_MAP.get(finish, FinishReason.stop),
            usage=Usage(
                input_tokens=u.get("prompt_tokens", 0),
                output_tokens=u.get("completion_tokens", 0),
            ),
            provider=self.provider_name,
        )

    def _transform_stream_request(self, request: ChatRequest) -> dict:
        p = self._transform_request(request)
        p["stream"]         = True
        p["stream_options"] = {"include_usage": True}
        return p

    def _parse_stream_event(self, raw_line: str) -> StreamEvent | None:
        try:
            data = json.loads(raw_line)
        except (json.JSONDecodeError, ValueError):
            return None

        choices = data.get("choices", [])
        u_raw   = data.get("usage")

        usage = None
        if u_raw:
            usage = Usage(
                input_tokens=u_raw.get("prompt_tokens", 0),
                output_tokens=u_raw.get("completion_tokens", 0),
            )

        if not choices:
            if usage:
                return MessageDeltaEvent(usage=usage)
            return None

        delta  = choices[0].get("delta", {})
        finish = choices[0].get("finish_reason")
        text   = delta.get("content")

        if delta.get("role") == "assistant" and not text:
            return MessageStartEvent(id=data.get("id", ""), model=data.get("model", ""))

        if text:
            return ContentDeltaEvent(index=0, delta=TextBlock(text=text))

        if finish:
            return MessageDeltaEvent(
                stop_reason=_FINISH_REASON_MAP.get(finish, FinishReason.stop),
                usage=usage,
            )

        return None


    async def get_model_detail(self, model_id: str) -> ModelDetail:
        await self._ensure_client()
        h    = {k: v for k, v in self._get_headers().items() if k != "Content-Type"}
        resp = await self._client.get(self._get_endpoint(f"/models/{model_id}"), headers=h)
        resp.raise_for_status()
        raw = resp.json()
        return ModelDetail(
            id=raw.get("id", model_id), name=raw.get("id", model_id),
            provider=self.provider_name, owned_by=raw.get("owned_by", ""),
            created=str(raw.get("created", "")),
        )

    async def count_tokens(self, request: TokenCountRequest) -> TokenCountResponse:
        try:
            import tiktoken
            enc   = tiktoken.encoding_for_model(request.model or self.get_default_model())
            total = sum(
                len(enc.encode(m.content if isinstance(m.content, str) else ""))
                for m in request.messages
            )
        except Exception:
            total = sum(
                len((m.content if isinstance(m.content, str) else "").split()) * 4 // 3
                for m in request.messages
            )
        return TokenCountResponse(
            input_tokens=total,
            model=request.model or self.get_default_model(),
            provider=self.provider_name,
        )
