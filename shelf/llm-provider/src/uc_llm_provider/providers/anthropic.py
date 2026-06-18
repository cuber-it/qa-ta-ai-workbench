"""
uc-llm-provider — Anthropic Provider
Unified → Anthropic → Unified

Anthropic ist dem Unified Interface am nächsten:
- system als First-Class-Feld ✓
- typed content blocks ✓
- tool_use / tool_result ✓
- thinking ✓
- cache_control ✓
- input_tokens / output_tokens ✓
"""
import json
import os

from ..core.base import BaseProvider
from ..core.models import (
    BatchCreateRequest,
    BatchListResponse,
    BatchResultItem,
    BatchResultsResponse,
    BatchStatus,
    ChatRequest,
    ChatResponse,
    ContentDeltaEvent,
    FinishReason,
    MessageDeltaEvent,
    MessageStartEvent,
    MessageStopEvent,
    ModelDetail,
    StreamEvent,
    TextBlock,
    ThinkingBlock,
    TokenCountRequest,
    TokenCountResponse,
    ToolUseBlock,
    Usage,
)

_FINISH_REASON_MAP = {
    "end_turn":   FinishReason.stop,
    "max_tokens": FinishReason.max_tokens,
    "tool_use":   FinishReason.tool_use,
}


class AnthropicProvider(BaseProvider):

    _tier1_core        = ["chat", "chat_stream", "models_list", "model_detail", "token_count"]
    _tier2_extended    = ["batches"]
    _tier3_specialized = []
    _features = {
        "tool_use": True, "vision": True, "web_search": True,
        "citations": True, "thinking": True, "cache_control": True,
        "embeddings": False, "audio": False, "images": False, "moderation": False,
        "top_k": True, "stop_sequences": True,
    }

    def _get_headers(self) -> dict:
        key = self.config.get("api_key") or os.getenv("ANTHROPIC_API_KEY", "")
        hdrs = {
            "x-api-key":         key,
            "anthropic-version": self.config.get("api_version", "2023-06-01"),
            "Content-Type":      "application/json",
        }
        if self.config.get("thinking") or self.config.get("extended_thinking"):
            hdrs["anthropic-beta"] = "interleaved-thinking-2025-05-14"
        return hdrs

    def _get_endpoint(self, path: str = "/messages") -> str:
        base = self.config.get("api_base", "https://api.anthropic.com/v1")
        return f"{base}{path}"


    def _transform_request(self, request: ChatRequest) -> dict:
        payload: dict = {
            "model":      request.model or self.get_default_model(),
            "max_tokens": request.max_tokens,
            "messages":   [self._to_anthropic_message(m) for m in request.messages],
        }
        sys_text = request.system_text()
        if sys_text:
            # system kann auch als Block-Liste mit cache_control übergeben werden
            if isinstance(request.system, list):
                payload["system"] = [self._to_anthropic_block(b) for b in request.system]
            else:
                payload["system"] = sys_text
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.stop_sequences:
            payload["stop_sequences"] = request.stop_sequences
        if request.tools:
            payload["tools"] = [
                {
                    "name":         t.name,
                    "description":  t.description or "",
                    "input_schema": t.input_schema,
                    **({"cache_control": t.cache_control.model_dump()} if t.cache_control else {}),
                }
                for t in request.tools
            ]
        if request.tool_choice:
            payload["tool_choice"] = request.tool_choice.model_dump()
        if request.thinking:
            payload["thinking"] = request.thinking.model_dump()
            if "anthropic-beta" not in self._get_headers():
                payload.setdefault("_beta_header", "interleaved-thinking-2025-05-14")
        if request.metadata:
            payload["metadata"] = request.metadata
        return payload

    def _to_anthropic_message(self, msg) -> dict:
        return {
            "role":    msg.role,
            "content": self._to_anthropic_content(msg.content),
        }

    def _to_anthropic_content(self, content) -> str | list:
        if isinstance(content, str):
            return content
        result = []
        for block in content:
            result.append(self._to_anthropic_block(block))
        return result

    def _to_anthropic_block(self, block) -> dict:
        t = block.type
        if t == "text":
            b: dict = {"type": "text", "text": block.text}
            if block.cache_control:
                b["cache_control"] = block.cache_control.model_dump()
            return b
        if t == "image":
            src = block.source
            if src.type == "base64":
                return {"type": "image", "source": {
                    "type": "base64", "media_type": src.media_type, "data": src.data,
                }}
            return {"type": "image", "source": {"type": "url", "url": src.url}}
        if t == "document":
            b = {"type": "document", "source": {
                "type": "base64", "media_type": "application/pdf", "data": block.source.data,
            }}
            if block.cache_control:
                b["cache_control"] = block.cache_control.model_dump()
            return b
        if t == "tool_use":
            return {"type": "tool_use", "id": block.id,
                    "name": block.name, "input": block.input}
        if t == "tool_result":
            b = {"type": "tool_result", "tool_use_id": block.tool_use_id}
            if isinstance(block.content, str):
                b["content"] = block.content
            else:
                b["content"] = [self._to_anthropic_block(c) for c in block.content]
            if block.is_error:
                b["is_error"] = True
            return b
        if t == "thinking":
            return {"type": "thinking", "thinking": block.thinking}
        return {"type": "text", "text": str(block)}


    def _transform_response(self, raw: dict) -> ChatResponse:
        content_blocks = []
        for b in raw.get("content", []):
            bt = b.get("type")
            if bt == "text":
                content_blocks.append(TextBlock(text=b["text"]))
            elif bt == "tool_use":
                content_blocks.append(ToolUseBlock(
                    id=b["id"], name=b["name"], input=b.get("input", {})
                ))
            elif bt == "thinking":
                content_blocks.append(ThinkingBlock(thinking=b.get("thinking", "")))

        u = raw.get("usage", {})
        usage = Usage(
            input_tokens=u.get("input_tokens", 0),
            output_tokens=u.get("output_tokens", 0),
            cache_read_tokens=u.get("cache_read_input_tokens", 0),
            cache_write_tokens=u.get("cache_creation_input_tokens", 0),
        )
        stop_reason = _FINISH_REASON_MAP.get(raw.get("stop_reason", ""), FinishReason.stop)

        return ChatResponse(
            id=raw.get("id", ""),
            model=raw.get("model", self.get_default_model()),
            content=content_blocks,
            stop_reason=stop_reason,
            usage=usage,
            provider=self.provider_name,
        )

    def _transform_stream_request(self, request: ChatRequest) -> dict:
        p = self._transform_request(request)
        p["stream"] = True
        return p

    def _parse_stream_event(self, raw_line: str) -> StreamEvent | None:
        try:
            ev = json.loads(raw_line)
        except json.JSONDecodeError:
            return None

        t = ev.get("type")

        if t == "message_start":
            msg = ev.get("message", {})
            u   = msg.get("usage", {})
            return MessageStartEvent(
                id=msg.get("id", ""),
                model=msg.get("model", ""),
                usage=Usage(input_tokens=u.get("input_tokens", 0)),
            )

        if t == "content_block_delta":
            delta = ev.get("delta", {})
            dt    = delta.get("type")
            idx   = ev.get("index", 0)
            if dt == "text_delta":
                txt = delta.get("text", "")
                return ContentDeltaEvent(index=idx, delta=TextBlock(text=txt)) if txt else None
            if dt == "thinking_delta":
                return ContentDeltaEvent(index=idx, delta=ThinkingBlock(thinking=delta.get("thinking", "")))

        if t == "message_delta":
            u       = ev.get("usage", {})
            reason  = ev.get("delta", {}).get("stop_reason", "")
            return MessageDeltaEvent(
                stop_reason=_FINISH_REASON_MAP.get(reason, FinishReason.stop),
                usage=Usage(output_tokens=u.get("output_tokens", 0)),
            )

        if t == "message_stop":
            return MessageStopEvent()

        return None


    async def get_model_detail(self, model_id: str) -> ModelDetail:
        await self._ensure_client()
        resp = await self._client.get(
            self._get_endpoint(f"/models/{model_id}"),
            headers=self._get_headers(),
        )
        resp.raise_for_status()
        d = resp.json()
        return ModelDetail(
            id=d.get("id", model_id),
            name=d.get("display_name", model_id),
            provider=self.provider_name,
            created=d.get("created_at"),
            owned_by="anthropic",
        )

    async def count_tokens(self, request: TokenCountRequest) -> TokenCountResponse:
        await self._ensure_client()
        model   = request.model or self.get_default_model()
        payload = self._transform_request(ChatRequest(
            model=model, messages=request.messages,
            system=request.system,
            tools=request.tools,
        ))
        resp = await self._client.post(
            self._get_endpoint("/messages/count_tokens"),
            headers=self._get_headers(), json=payload,
        )
        resp.raise_for_status()
        return TokenCountResponse(
            input_tokens=resp.json().get("input_tokens", 0),
            model=model, provider=self.provider_name,
        )


    async def create_batch(self, request: BatchCreateRequest) -> BatchStatus:
        await self._ensure_client()
        model = request.model or self.get_default_model()
        reqs  = [{"custom_id": item.custom_id,
                  "params": {**item.params, "model": model}}
                 for item in request.requests]
        resp = await self._client.post(
            self._get_endpoint("/messages/batches"),
            headers=self._get_headers(), json={"requests": reqs},
        )
        resp.raise_for_status()
        return self._parse_batch(resp.json())

    async def list_batches(self) -> BatchListResponse:
        await self._ensure_client()
        resp = await self._client.get(self._get_endpoint("/messages/batches"),
                                      headers=self._get_headers())
        resp.raise_for_status()
        d = resp.json()
        return BatchListResponse(
            batches=[self._parse_batch(b) for b in d.get("data", d.get("batches", []))],
            provider=self.provider_name,
        )

    async def get_batch(self, batch_id: str) -> BatchStatus:
        await self._ensure_client()
        resp = await self._client.get(
            self._get_endpoint(f"/messages/batches/{batch_id}"),
            headers=self._get_headers())
        resp.raise_for_status()
        return self._parse_batch(resp.json())

    async def cancel_batch(self, batch_id: str) -> BatchStatus:
        await self._ensure_client()
        resp = await self._client.post(
            self._get_endpoint(f"/messages/batches/{batch_id}/cancel"),
            headers=self._get_headers())
        resp.raise_for_status()
        return self._parse_batch(resp.json())

    async def get_batch_results(self, batch_id: str) -> BatchResultsResponse:
        await self._ensure_client()
        resp = await self._client.get(
            self._get_endpoint(f"/messages/batches/{batch_id}/results"),
            headers=self._get_headers())
        resp.raise_for_status()
        results = [
            BatchResultItem(
                custom_id=json.loads(line).get("custom_id", ""),
                result=json.loads(line).get("result"),
                error=json.loads(line).get("error"),
            )
            for line in resp.text.strip().split("\n") if line.strip()
        ]
        return BatchResultsResponse(batch_id=batch_id, results=results,
                                    provider=self.provider_name)

    def _parse_batch(self, d: dict) -> BatchStatus:
        c = d.get("request_counts", {})
        return BatchStatus(
            id=d.get("id", ""),
            status=d.get("processing_status", d.get("status", "unknown")),
            total_requests=c.get("total"),
            completed_requests=c.get("succeeded"),
            failed_requests=c.get("errored"),
            created_at=d.get("created_at"),
            ended_at=d.get("ended_at"),
            provider=self.provider_name,
        )
