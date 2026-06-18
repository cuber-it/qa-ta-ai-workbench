"""
uc-llm-provider — Google Gemini Provider
Tier 1: chat, chat_stream, models, model_detail, token_count
Tier 2: embeddings
Tier 3: –

Google Gemini API Besonderheiten:
- Endpoint: generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
- Rollen: "user" und "model" (nicht "assistant")
- Content-Format: {parts: [{text: "..."}]}
- API-Key über Query-Parameter
- Streaming: :streamGenerateContent?alt=sse
"""
import json
import os
import time

from ..core.base import BaseProvider
from ..core.models import (
    ChatRequest,
    ChatResponse,
    ContentDeltaEvent,
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    ErrorEvent,
    FinishReason,
    MessageDeltaEvent,
    ModelDetail,
    StreamEvent,
    TextBlock,
    TokenCountRequest,
    TokenCountResponse,
    ToolUseBlock,
    Usage,
)


class GoogleProvider(BaseProvider):

    _tier1_core = ["chat", "chat_stream", "models_list", "model_detail", "token_count"]
    _tier2_extended = ["embeddings"]
    _tier3_specialized = []

    _features = {
        "tool_use": True, "vision": True, "web_search": True,
        "citations": False, "thinking": True, "cache_control": False,
        "embeddings": True, "audio": False, "images": False, "moderation": False,
    }


    def _api_key(self) -> str:
        return self.config.get("api_key") or os.getenv("GOOGLE_API_KEY", "")

    def _get_headers(self) -> dict:
        return {"Content-Type": "application/json"}

    def _get_endpoint(self, model: str = "") -> str:
        base = self.config.get("api_base", "https://generativelanguage.googleapis.com/v1beta")
        m = model or self.config.get("default_model", "gemini-2.0-flash")
        return f"{base}/models/{m}:generateContent?key={self._api_key()}"

    def _get_stream_endpoint(self, model: str) -> str:
        base = self.config.get("api_base", "https://generativelanguage.googleapis.com/v1beta")
        return f"{base}/models/{model}:streamGenerateContent?alt=sse&key={self._api_key()}"

    def _get_token_count_endpoint(self, model: str) -> str:
        base = self.config.get("api_base", "https://generativelanguage.googleapis.com/v1beta")
        return f"{base}/models/{model}:countTokens?key={self._api_key()}"

    def _get_embed_endpoint(self, model: str) -> str:
        base = self.config.get("api_base", "https://generativelanguage.googleapis.com/v1beta")
        return f"{base}/models/{model}:embedContent?key={self._api_key()}"

    def _role(self, role: str) -> str:
        """Anthropic/OpenAI roles → Gemini roles."""
        return "model" if role == "assistant" else "user"

    def _to_contents(self, messages) -> list:
        """
        Wandelt Messages in Gemini-contents um.
        Gemini erwartet alternierend user/model — aufeinanderfolgende
        gleiche Rollen werden zusammengeführt.
        """
        contents = []
        for msg in messages:
            role = self._role(msg.role)
            parts = self._gemini_parts(msg.content)
            # Gleiche Rollen hintereinander zusammenführen
            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"].extend(parts)
            else:
                contents.append({"role": role, "parts": parts})
        return contents

    def _gemini_parts(self, content) -> list:
        if isinstance(content, str) or content is None:
            return [{"text": content or ""}]
        result = []
        for p in content:
            if hasattr(p, "type"):
                if p.type == "text":
                    result.append({"text": p.text})
                elif p.type == "image_url":
                    url = p.image_url.url
                    if url.startswith("data:"):
                        media, data = url[5:].split(";base64,", 1)
                        result.append({"inline_data": {"mime_type": media, "data": data}})
                    else:
                        result.append({"text": f"[image: {url}]"})
            elif isinstance(p, dict):
                result.append({"text": str(p)})
        return result or [{"text": ""}]

    def _build_payload(self, request: ChatRequest) -> dict:
        payload: dict = {
            "contents": self._to_contents(request.messages),
            "generationConfig": {},
        }
        # system ist First-Class-Feld in ChatRequest
        sys_text = request.system_text()
        if sys_text:
            payload["system_instruction"] = {"parts": [{"text": sys_text}]}
        if request.max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = request.max_tokens
        if request.temperature is not None:
            payload["generationConfig"]["temperature"] = request.temperature
        if request.top_p is not None:
            payload["generationConfig"]["topP"] = request.top_p
        if request.stop_sequences:
            stops = request.stop_sequences
            payload["generationConfig"]["stopSequences"] = stops
        if not payload["generationConfig"]:
            del payload["generationConfig"]
        if request.tools:
            payload["tools"] = [{"function_declarations": [
                {"name": t.function.name,
                 "description": t.function.description or "",
                 "parameters": t.function.parameters or {}}
                for t in request.tools
            ]}]
        return payload


    def _transform_request(self, request: ChatRequest) -> dict:
        return self._build_payload(request)

    def _transform_stream_request(self, request: ChatRequest) -> dict:
        return self._build_payload(request)

    def _transform_response(self, raw: dict) -> ChatResponse:
        candidates = raw.get("candidates", [])
        content_blocks = []
        finish = FinishReason.stop

        if candidates:
            cand   = candidates[0]
            reason = cand.get("finishReason", "STOP")
            finish = {
                "STOP": FinishReason.stop, "MAX_TOKENS": FinishReason.max_tokens,
                "TOOL_CODE": FinishReason.tool_use,
            }.get(reason, FinishReason.stop)
            for part in cand.get("content", {}).get("parts", []):
                if "text" in part:
                    content_blocks.append(TextBlock(text=part["text"]))
                elif "functionCall" in part:
                    fc = part["functionCall"]
                    content_blocks.append(ToolUseBlock(
                        id=f"call_{fc.get('name', '')}",
                        name=fc.get("name", ""),
                        input=fc.get("args", {}),
                    ))

        u = raw.get("usageMetadata", {})
        return ChatResponse(
            model=raw.get("modelVersion", self.get_default_model()),
            content=content_blocks,
            stop_reason=finish,
            usage=Usage(
                input_tokens=u.get("promptTokenCount", 0),
                output_tokens=u.get("candidatesTokenCount", 0),
            ),
            provider=self.provider_name,
        )

    def _parse_stream_event(self, raw_line: str) -> StreamEvent | None:
        try:
            ev = json.loads(raw_line)
        except json.JSONDecodeError:
            return None

        candidates = ev.get("candidates", [])
        u          = ev.get("usageMetadata", {})
        usage      = None
        if u:
            usage = Usage(
                input_tokens=u.get("promptTokenCount", 0),
                output_tokens=u.get("candidatesTokenCount", 0),
            )

        if not candidates:
            return MessageDeltaEvent(usage=usage) if usage else None

        cand   = candidates[0]
        finish = cand.get("finishReason")
        parts  = cand.get("content", {}).get("parts", [])
        text   = "".join(p.get("text", "") for p in parts if "text" in p)

        if finish in ("STOP", "MAX_TOKENS"):
            reason = FinishReason.stop if finish == "STOP" else FinishReason.max_tokens
            return MessageDeltaEvent(stop_reason=reason, usage=usage)

        if text:
            return ContentDeltaEvent(index=0, delta=TextBlock(text=text))

        return None


    async def chat(self, request: ChatRequest) -> ChatResponse:
        await self._ensure_client()
        start  = time.perf_counter()
        status = "success"
        err    = None
        in_tok = out_tok = 0
        model  = request.model or self.get_default_model()
        ctx    = self._ctx(request)
        payload = self._build_payload(request)
        self.logger.log_request("/chat", payload, **ctx)
        try:
            resp   = await self._client.post(
                self._get_endpoint(model), headers=self._get_headers(), json=payload)
            resp.raise_for_status()
            result  = self._transform_response(resp.json())
            in_tok  = result.usage.input_tokens
            out_tok = result.usage.output_tokens
            self.logger.log_response("/chat", resp.status_code, result.model_dump(), **ctx)
            return result
        except Exception as e:
            status = "error"
            err    = str(e)
            self.logger.log_error("/chat", err, **ctx)
            raise
        finally:
            ms = int((time.perf_counter() - start) * 1000)
            self._log_cost_sync(model, in_tok, out_tok, ms, ctx, status, err)

    async def chat_stream(self, request: ChatRequest):
        await self._ensure_client()
        start  = time.perf_counter()
        status = "success"
        err    = None
        in_tok = out_tok = 0
        model  = request.model or self.get_default_model()
        ctx    = self._ctx(request)
        payload = self._build_payload(request)
        self.logger.log_request("/chat/stream", payload, **ctx)
        try:
            async with self._client.stream(
                "POST", self._get_stream_endpoint(model),
                headers=self._get_headers(), json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if not data or data == "[DONE]":
                        break
                    event = self._parse_stream_event(data)
                    if event is None:
                        continue
                    if hasattr(event, "usage") and event.usage:
                        in_tok  = event.usage.input_tokens  or in_tok
                        out_tok = event.usage.output_tokens or out_tok
                    yield event
        except Exception as e:
            status = "error"
            err    = str(e)
            self.logger.log_error("/chat/stream", err, **ctx)
            yield ErrorEvent(message=err)
        finally:
            ms = int((time.perf_counter() - start) * 1000)
            self._log_cost_sync(model, in_tok, out_tok, ms, ctx, status, err)


    async def get_model_detail(self, model_id: str) -> ModelDetail:
        await self._ensure_client()
        base = self.config.get("api_base", "https://generativelanguage.googleapis.com/v1beta")
        url = f"{base}/models/{model_id}?key={self._api_key()}"
        resp = await self._client.get(url, headers=self._get_headers())
        resp.raise_for_status()
        d = resp.json()
        return ModelDetail(
            id=d.get("name", model_id).split("/")[-1],
            name=d.get("displayName", model_id),
            provider=self.provider_name,
            created=None,
            owned_by="google",
        )


    async def count_tokens(self, request: TokenCountRequest) -> TokenCountResponse:
        await self._ensure_client()
        model   = request.model or self.get_default_model()
        payload: dict = {"contents": self._to_contents(request.messages)}
        if request.system:
            payload["system_instruction"] = {"parts": [{"text": request.system}]}
        resp = await self._client.post(
            self._get_token_count_endpoint(model),
            headers=self._get_headers(), json=payload,
        )
        resp.raise_for_status()
        return TokenCountResponse(
            input_tokens=resp.json().get("totalTokens", 0),
            model=model, provider=self.provider_name,
        )


    async def create_embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        await self._ensure_client()
        model = request.model or self.config.get(
            "embedding_model", "text-embedding-004")
        texts = request.input if isinstance(request.input, list) else [request.input]
        data = []
        for i, text in enumerate(texts):
            payload = {"content": {"parts": [{"text": text}]}}
            resp = await self._client.post(
                self._get_embed_endpoint(model),
                headers=self._get_headers(), json=payload,
            )
            resp.raise_for_status()
            values = resp.json().get("embedding", {}).get("values", [])
            data.append(EmbeddingData(index=i, embedding=values))
        return EmbeddingResponse(
            data=data, model=model,
            usage={"prompt_tokens": len(texts), "total_tokens": len(texts)},
            provider=self.provider_name,
        )
