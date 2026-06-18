"""
OpenAI Tier 2 Mixin — Embeddings und Batches.
Wird von OpenAIProvider geerbt.
"""
import json

from ..core.models import (
    BatchCreateRequest,
    BatchListResponse,
    BatchResultItem,
    BatchResultsResponse,
    BatchStatus,
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
)


class OpenAITier2Mixin:

    async def create_embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        await self._ensure_client()
        model = request.model or self.config.get("embedding_model", "text-embedding-3-small")
        payload = {"model": model, "input": request.input}
        if request.encoding_format:
            payload["encoding_format"] = request.encoding_format
        if request.dimensions:
            payload["dimensions"] = request.dimensions
        resp = await self._client.post(
            self._get_endpoint("/embeddings"), headers=self._get_headers(), json=payload)
        resp.raise_for_status()
        raw = resp.json()
        data = [EmbeddingData(index=i["index"], embedding=i["embedding"]) for i in raw.get("data", [])]
        return EmbeddingResponse(
            data=data, model=raw.get("model", model),
            usage={
                "prompt_tokens": raw.get("usage", {}).get("prompt_tokens", 0),
                "total_tokens":  raw.get("usage", {}).get("total_tokens", 0),
            },
            provider=self.provider_name,
        )

    async def create_batch(self, request: BatchCreateRequest) -> BatchStatus:
        await self._ensure_client()
        model = request.model or self.get_default_model()
        lines = []
        for item in request.requests:
            p = dict(item.params)
            p.setdefault("model", model)
            lines.append(json.dumps({
                "custom_id": item.custom_id, "method": "POST",
                "url": "/v1/chat/completions", "body": p,
            }))
        jsonl = "\n".join(lines)
        h = {k: v for k, v in self._get_headers().items() if k != "Content-Type"}
        fr = await self._client.post(
            self._get_endpoint("/files"), headers=h,
            files={"file": ("batch.jsonl", jsonl.encode(), "application/jsonl")},
            data={"purpose": "batch"},
        )
        fr.raise_for_status()
        file_id = fr.json()["id"]
        resp = await self._client.post(
            self._get_endpoint("/batches"), headers=self._get_headers(),
            json={"input_file_id": file_id, "endpoint": "/v1/chat/completions",
                  "completion_window": "24h"},
        )
        resp.raise_for_status()
        return self._parse_batch(resp.json())

    async def list_batches(self) -> BatchListResponse:
        await self._ensure_client()
        h = {k: v for k, v in self._get_headers().items() if k != "Content-Type"}
        resp = await self._client.get(self._get_endpoint("/batches"), headers=h)
        resp.raise_for_status()
        return BatchListResponse(
            batches=[self._parse_batch(b) for b in resp.json().get("data", [])],
            provider=self.provider_name,
        )

    async def get_batch(self, batch_id: str) -> BatchStatus:
        await self._ensure_client()
        h = {k: v for k, v in self._get_headers().items() if k != "Content-Type"}
        resp = await self._client.get(self._get_endpoint(f"/batches/{batch_id}"), headers=h)
        resp.raise_for_status()
        return self._parse_batch(resp.json())

    async def cancel_batch(self, batch_id: str) -> BatchStatus:
        await self._ensure_client()
        resp = await self._client.post(
            self._get_endpoint(f"/batches/{batch_id}/cancel"), headers=self._get_headers())
        resp.raise_for_status()
        return self._parse_batch(resp.json())

    async def get_batch_results(self, batch_id: str) -> BatchResultsResponse:
        await self._ensure_client()
        h = {k: v for k, v in self._get_headers().items() if k != "Content-Type"}
        br = await self._client.get(self._get_endpoint(f"/batches/{batch_id}"), headers=h)
        br.raise_for_status()
        ofid = br.json().get("output_file_id")
        if not ofid:
            return BatchResultsResponse(batch_id=batch_id, results=[], provider=self.provider_name)
        fr = await self._client.get(self._get_endpoint(f"/files/{ofid}/content"), headers=h)
        fr.raise_for_status()
        results = []
        for line in fr.text.strip().split("\n"):
            if not line.strip():
                continue
            e = json.loads(line)
            results.append(BatchResultItem(
                custom_id=e.get("custom_id", ""),
                result=e.get("response", {}).get("body"),
                error=e.get("error"),
            ))
        return BatchResultsResponse(batch_id=batch_id, results=results, provider=self.provider_name)

    def _parse_batch(self, d: dict) -> BatchStatus:
        c = d.get("request_counts", {})
        return BatchStatus(
            id=d.get("id", ""), status=d.get("status", "unknown"),
            total_requests=c.get("total"), completed_requests=c.get("completed"),
            failed_requests=c.get("failed"), created_at=str(d.get("created_at", "")),
            ended_at=str(d.get("completed_at", "")), provider=self.provider_name,
        )
