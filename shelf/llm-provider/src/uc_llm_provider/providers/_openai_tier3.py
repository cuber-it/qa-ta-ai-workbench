"""
OpenAI Tier 3 Mixin — Moderation, Audio, Images.
Wird von OpenAIProvider geerbt.
"""
from ..core.models import (
    AudioResponse,
    AudioSpeechRequest,
    ImageData,
    ImageEditRequest,
    ImageGenerationRequest,
    ImageResponse,
    ImageVariationRequest,
    ModerationRequest,
    ModerationResponse,
    ModerationResult,
)


class OpenAITier3Mixin:

    async def create_moderation(self, request: ModerationRequest) -> ModerationResponse:
        await self._ensure_client()
        payload = {"input": request.input}
        if request.model:
            payload["model"] = request.model
        resp = await self._client.post(
            self._get_endpoint("/moderations"), headers=self._get_headers(), json=payload)
        resp.raise_for_status()
        raw = resp.json()
        return ModerationResponse(
            id=raw.get("id", ""),
            results=[ModerationResult(
                flagged=r["flagged"],
                categories=r["categories"],
                category_scores=r["category_scores"],
            ) for r in raw.get("results", [])],
            model=raw.get("model", ""), provider=self.provider_name,
        )

    async def transcribe_audio(self, file_bytes: bytes, filename: str, **kw) -> AudioResponse:
        await self._ensure_client()
        model = kw.get("model") or self.config.get("audio_model", "whisper-1")
        h = {k: v for k, v in self._get_headers().items() if k != "Content-Type"}
        data = {"model": model}
        for k in ("language", "prompt", "response_format"):
            if kw.get(k):
                data[k] = kw[k]
        if kw.get("temperature") is not None:
            data["temperature"] = str(kw["temperature"])
        resp = await self._client.post(
            self._get_endpoint("/audio/transcriptions"), headers=h,
            files={"file": (filename, file_bytes, "audio/mpeg")}, data=data)
        resp.raise_for_status()
        raw = resp.json() if "application/json" in resp.headers.get("content-type", "") else {"text": resp.text}
        return AudioResponse(text=raw.get("text", resp.text), model=model, provider=self.provider_name)

    async def translate_audio(self, file_bytes: bytes, filename: str, **kw) -> AudioResponse:
        await self._ensure_client()
        model = kw.get("model") or self.config.get("audio_model", "whisper-1")
        h = {k: v for k, v in self._get_headers().items() if k != "Content-Type"}
        data = {"model": model}
        for k in ("prompt", "response_format"):
            if kw.get(k):
                data[k] = kw[k]
        if kw.get("temperature") is not None:
            data["temperature"] = str(kw["temperature"])
        resp = await self._client.post(
            self._get_endpoint("/audio/translations"), headers=h,
            files={"file": (filename, file_bytes, "audio/mpeg")}, data=data)
        resp.raise_for_status()
        raw = resp.json() if "application/json" in resp.headers.get("content-type", "") else {"text": resp.text}
        return AudioResponse(text=raw.get("text", resp.text), model=model, provider=self.provider_name)

    async def create_speech(self, request: AudioSpeechRequest) -> bytes:
        await self._ensure_client()
        model = request.model or self.config.get("tts_model", "tts-1")
        payload: dict = {"model": model, "input": request.input, "voice": request.voice}
        if request.response_format:
            payload["response_format"] = request.response_format
        if request.speed is not None:
            payload["speed"] = request.speed
        resp = await self._client.post(
            self._get_endpoint("/audio/speech"), headers=self._get_headers(), json=payload)
        resp.raise_for_status()
        return resp.content

    async def generate_image(self, request: ImageGenerationRequest) -> ImageResponse:
        await self._ensure_client()
        model = request.model or self.config.get("image_model", "dall-e-3")
        payload: dict = {"model": model, "prompt": request.prompt, "n": request.n}
        for k in ("size", "quality", "style", "response_format"):
            v = getattr(request, k, None)
            if v:
                payload[k] = v
        resp = await self._client.post(
            self._get_endpoint("/images/generations"), headers=self._get_headers(), json=payload)
        resp.raise_for_status()
        return self._parse_img(resp.json(), model)

    async def edit_image(self, image_bytes: bytes, request: ImageEditRequest,
                         mask_bytes: bytes | None = None) -> ImageResponse:
        await self._ensure_client()
        model = request.model or "dall-e-2"
        h = {k: v for k, v in self._get_headers().items() if k != "Content-Type"}
        files = {"image": ("image.png", image_bytes, "image/png")}
        if mask_bytes:
            files["mask"] = ("mask.png", mask_bytes, "image/png")
        data = {"prompt": request.prompt, "model": model, "n": str(request.n)}
        if request.size:
            data["size"] = request.size
        resp = await self._client.post(
            self._get_endpoint("/images/edits"), headers=h, files=files, data=data)
        resp.raise_for_status()
        return self._parse_img(resp.json(), model)

    async def create_image_variation(self, image_bytes: bytes,
                                     request: ImageVariationRequest) -> ImageResponse:
        await self._ensure_client()
        model = request.model or "dall-e-2"
        h = {k: v for k, v in self._get_headers().items() if k != "Content-Type"}
        files = {"image": ("image.png", image_bytes, "image/png")}
        data = {"model": model, "n": str(request.n)}
        if request.size:
            data["size"] = request.size
        resp = await self._client.post(
            self._get_endpoint("/images/variations"), headers=h, files=files, data=data)
        resp.raise_for_status()
        return self._parse_img(resp.json(), model)

    def _parse_img(self, raw: dict, model: str) -> ImageResponse:
        return ImageResponse(
            data=[ImageData(
                url=i.get("url"),
                b64_json=i.get("b64_json"),
                revised_prompt=i.get("revised_prompt"),
            ) for i in raw.get("data", [])],
            model=model, provider=self.provider_name,
        )
