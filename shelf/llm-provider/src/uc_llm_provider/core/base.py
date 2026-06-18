"""
uc-llm-provider — BaseProvider
"""
import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import httpx

from ..logging.cost_logger import get_cost_logger
from ..logging.request_logger import RequestResponseLogger
from .models import (
    AudioResponse,
    AudioSpeechRequest,
    BatchCreateRequest,
    BatchListResponse,
    BatchResultsResponse,
    BatchStatus,
    CapabilitiesResponse,
    CapabilityTier,
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    ErrorEvent,
    HealthResponse,
    ImageEditRequest,
    ImageGenerationRequest,
    ImageResponse,
    ImageVariationRequest,
    ModelDetail,
    ModerationRequest,
    ModerationResponse,
    NotImplementedResponse,
    StreamEvent,
    TokenCountRequest,
    TokenCountResponse,
)
from .retry import RateLimitHit, RetryExhausted, with_retry


class EndpointNotAvailable(Exception):
    def __init__(self, endpoint: str, provider: str):
        self.endpoint = endpoint
        self.provider = provider
        self.detail   = NotImplementedResponse(
            endpoint=endpoint, provider=provider,
            message=f"'{endpoint}' is not available for provider '{provider}'"
        )
        super().__init__(self.detail.message)


class BaseProvider(ABC):

    _tier1_core:        list[str] = []
    _tier2_extended:    list[str] = []
    _tier3_specialized: list[str] = []
    _features:          dict      = {}

    def __init__(
        self,
        config: dict,
        logger: RequestResponseLogger | None = None,
        cost_logger=None,
    ):
        self.config        = config
        self.provider_name = config.get("name", "unknown")
        self._client:      httpx.AsyncClient | None = None
        log_dir            = os.environ.get("UC_LLM_LOG_DIR", "./logs")
        log_requests       = os.environ.get("UC_LLM_LOG_REQUESTS", "false").lower() == "true"
        self.logger        = logger or RequestResponseLogger(self.provider_name, log_dir, enabled=log_requests)
        self._cost         = cost_logger or get_cost_logger()
        throttle_cfg       = config.get("throttle") or {}
        self._min_interval = float(throttle_cfg.get("min_interval_s", 0.0))
        self._last_req_ts  = 0.0
        self._rate_limit_hits: list = []
        self._usage_log    = logging.getLogger(f"uc_llm.{self.provider_name}.usage")

    @abstractmethod
    def _get_headers(self) -> dict: ...

    @abstractmethod
    def _get_endpoint(self, path: str = "") -> str: ...

    @abstractmethod
    def _transform_request(self, request: ChatRequest) -> dict: ...

    @abstractmethod
    def _transform_response(self, raw: dict) -> ChatResponse: ...

    @abstractmethod
    def _transform_stream_request(self, request: ChatRequest) -> dict: ...

    @abstractmethod
    def _parse_stream_event(self, raw_line: str) -> StreamEvent | None: ...

    def _ts(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _not_impl(self, endpoint: str):
        raise EndpointNotAvailable(endpoint, self.provider_name)

    def _ctx(self, request) -> dict:
        ctx = request.context
        if ctx is None:
            return {}
        return {
            "session_id": ctx.session_id or "",
            "caller_id":  ctx.caller_id  or "",
            "task_id":    ctx.task_id    or "",
        }

    async def _throttle(self) -> None:
        if self._min_interval <= 0:
            return
        wait = self._min_interval - (time.monotonic() - self._last_req_ts)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_req_ts = time.monotonic()

    async def _ensure_client(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)

    def _log_cost_sync(self, model, in_tok, out_tok, ms, ctx, status, err=None):
        ctx = ctx or {}
        self._usage_log.info("model=%s in=%d out=%d latency=%dms status=%s",
                             model, in_tok, out_tok, ms, status)
        self._cost.log(
            provider=self.provider_name, model=model,
            input_tokens=in_tok, output_tokens=out_tok,
            latency_ms=ms, status=status, error_message=err,
            caller_id=ctx.get("caller_id", ""),
            session_id=ctx.get("session_id", ""),
            task_id=ctx.get("task_id", ""),
        )

    def health(self) -> HealthResponse:
        return HealthResponse(
            status="ok" if self._client is not None else "idle",
            provider=self.provider_name,
            timestamp=self._ts(),
        )

    def get_capabilities(self) -> CapabilitiesResponse:
        return CapabilitiesResponse(
            provider=self.provider_name,
            tiers=CapabilityTier(
                core=self._tier1_core,
                extended=self._tier2_extended,
                specialized=self._tier3_specialized,
            ),
            features=self._features,
        )

    def get_models(self) -> list[str]:
        return self.config.get("models", [self.get_default_model()])

    def get_default_model(self) -> str:
        return self.config.get("default_model", "unknown")

    async def get_model_detail(self, model_id: str) -> ModelDetail:
        self._not_impl("GET /models/{id}")

    async def count_tokens(self, request: TokenCountRequest) -> TokenCountResponse:
        self._not_impl("POST /tokens/count")

    async def chat(self, request: ChatRequest) -> ChatResponse:
        await self._ensure_client()
        start  = time.perf_counter()
        status = "success"
        err    = None
        in_tok = out_tok = 0
        model  = request.model or self.get_default_model()
        ctx    = self._ctx(request)
        payload = self._transform_request(request)
        if request.extra:
            payload.update(request.extra)
        headers = self._get_headers()
        if request.extra_headers:
            headers.update(request.extra_headers)
        self.logger.log_request("/chat", payload, **ctx)

        async def _do():
            await self._throttle()
            resp = await self._client.post(
                self._get_endpoint(), headers=headers, json=payload
            )
            resp.raise_for_status()
            return resp

        try:
            resp    = await with_retry(_do, self.config, self._rate_limit_hits)
            result  = self._transform_response(resp.json())
            in_tok  = result.usage.input_tokens
            out_tok = result.usage.output_tokens
            model   = result.model
            self.logger.log_response("/chat", resp.status_code, result.model_dump(), **ctx)
            return result
        except RateLimitHit as e:
            status = "rate_limit"
            err = str(e)
            self.logger.log_error("/chat", err, **ctx)
            raise Exception(err) from e
        except RetryExhausted as e:
            status = "error"
            err = str(e)
            self.logger.log_error("/chat", err, **ctx)
            raise Exception(err) from e
        except httpx.HTTPStatusError as e:
            status = "error"
            try:
                body   = e.response.json()
                detail = body.get("error", body)
                err    = detail.get("message", str(detail)) if isinstance(detail, dict) else str(detail)
            except Exception:
                err = e.response.text or str(e)
            self.logger.log_error("/chat", err, **ctx)
            raise Exception(err) from e
        except Exception as e:
            status = "error"
            err = str(e)
            self.logger.log_error("/chat", err, **ctx)
            raise
        finally:
            ms = int((time.perf_counter() - start) * 1000)
            self._log_cost_sync(model, in_tok, out_tok, ms, ctx, status, err)

    async def chat_stream(self, request: ChatRequest) -> AsyncGenerator[StreamEvent, None]:
        await self._ensure_client()
        start  = time.perf_counter()
        status = "success"
        err    = None
        in_tok = out_tok = 0
        model  = request.model or self.get_default_model()
        ctx    = self._ctx(request)
        payload = self._transform_stream_request(request)
        if request.extra:
            payload.update(request.extra)
        headers = self._get_headers()
        if request.extra_headers:
            headers.update(request.extra_headers)
        self.logger.log_request("/chat/stream", payload, **ctx)

        try:
            await self._throttle()
            async with self._client.stream(
                "POST", self._get_endpoint(),
                headers=headers, json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    event = self._parse_stream_event(data)
                    if event is None:
                        continue
                    if hasattr(event, "usage") and event.usage:
                        in_tok  = event.usage.input_tokens  or in_tok
                        out_tok = event.usage.output_tokens or out_tok
                    yield event
        except httpx.HTTPStatusError as e:
            status = "error"
            try:
                await e.response.aread()
                err = str(e.response.json().get("error", e.response.text))
            except Exception:
                err = str(e)
            self.logger.log_error("/chat/stream", err, **ctx)
            yield ErrorEvent(message=err)
        except Exception as e:
            status = "error"
            err = str(e)
            self.logger.log_error("/chat/stream", err, **ctx)
            yield ErrorEvent(message=err)
        finally:
            ms = int((time.perf_counter() - start) * 1000)
            self._log_cost_sync(model, in_tok, out_tok, ms, ctx, status, err)

    async def create_embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self._not_impl("POST /embeddings")

    async def create_batch(self, request: BatchCreateRequest) -> BatchStatus:
        self._not_impl("POST /batches")

    async def list_batches(self) -> BatchListResponse:
        self._not_impl("GET /batches")

    async def get_batch(self, batch_id: str) -> BatchStatus:
        self._not_impl("GET /batches/{id}")

    async def cancel_batch(self, batch_id: str) -> BatchStatus:
        self._not_impl("POST /batches/{id}/cancel")

    async def get_batch_results(self, batch_id: str) -> BatchResultsResponse:
        self._not_impl("GET /batches/{id}/results")

    async def create_moderation(self, request: ModerationRequest) -> ModerationResponse:
        self._not_impl("POST /moderations")

    async def transcribe_audio(self, file_bytes: bytes, filename: str, **kw) -> AudioResponse:
        self._not_impl("POST /audio/transcriptions")

    async def translate_audio(self, file_bytes: bytes, filename: str, **kw) -> AudioResponse:
        self._not_impl("POST /audio/translations")

    async def create_speech(self, request: AudioSpeechRequest) -> bytes:
        self._not_impl("POST /audio/speech")

    async def generate_image(self, request: ImageGenerationRequest) -> ImageResponse:
        self._not_impl("POST /images/generations")

    async def edit_image(self, image_bytes: bytes, request: ImageEditRequest,
                         mask_bytes: bytes | None = None) -> ImageResponse:
        self._not_impl("POST /images/edits")

    async def create_image_variation(self, image_bytes: bytes,
                                     request: ImageVariationRequest) -> ImageResponse:
        self._not_impl("POST /images/variations")
