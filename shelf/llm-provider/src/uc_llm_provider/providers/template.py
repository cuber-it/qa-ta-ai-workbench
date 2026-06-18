"""
Template für neue Provider.
Kopieren, umbenennen, _get_headers und _get_endpoint anpassen — fertig.
"""
import json

from ..core.base import BaseProvider
from ..core.models import (
    ChatRequest,
    ChatResponse,
    ContentDeltaEvent,
    FinishReason,
    MessageDeltaEvent,
    StreamEvent,
    TextBlock,
    Usage,
)


class TemplateProvider(BaseProvider):
    _tier1_core        = ["chat", "chat_stream"]
    _tier2_extended    = []
    _tier3_specialized = []
    _features          = {}

    def _get_headers(self) -> dict:
        return {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self.config.get('api_key', '')}",
        }

    def _get_endpoint(self, path: str = "") -> str:
        return f"{self.config.get('api_base', '').rstrip('/')}/chat/completions"

    def _transform_request(self, request: ChatRequest) -> dict:
        msgs = []
        sys_text = request.system_text()
        if sys_text:
            msgs.append({"role": "system", "content": sys_text})
        for m in request.messages:
            msgs.append({"role": m.role, "content": m.content if isinstance(m.content, str) else ""})
        return {"model": request.model or self.get_default_model(),
                "messages": msgs, "max_tokens": request.max_tokens}

    def _transform_response(self, raw: dict) -> ChatResponse:
        ch = raw["choices"][0]
        u  = raw.get("usage", {})
        return ChatResponse(
            model=raw.get("model", self.get_default_model()),
            content=[TextBlock(text=ch["message"].get("content") or "")],
            stop_reason=FinishReason.stop,
            usage=Usage(
                input_tokens=u.get("prompt_tokens", 0),
                output_tokens=u.get("completion_tokens", 0),
            ),
            provider=self.provider_name,
        )

    def _transform_stream_request(self, request: ChatRequest) -> dict:
        return {**self._transform_request(request), "stream": True}

    def _parse_stream_event(self, raw_line: str) -> StreamEvent | None:
        try:
            data   = json.loads(raw_line)
            delta  = data["choices"][0].get("delta", {})
            finish = data["choices"][0].get("finish_reason")
            text   = delta.get("content")
            if text:
                return ContentDeltaEvent(index=0, delta=TextBlock(text=text))
            if finish:
                return MessageDeltaEvent(stop_reason=FinishReason.stop)
        except Exception:
            pass
        return None
