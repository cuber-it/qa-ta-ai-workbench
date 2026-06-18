"""
Ollama Provider — lokale LLMs via Ollama (https://ollama.com).

Ollama exposes an OpenAI-compatible /v1/chat/completions endpoint.
Zusätzlich: native Ollama-API für Modell-Management (pull, list, delete).

Config (YAML):
    name: ollama
    provider_type: ollama
    api_base: http://localhost:11434
    default_model: llama3.2
    models:
      - llama3.2
      - mistral
      - phi3
    throttle:
      min_interval_s: 0.1

Usage:
    from uc_llm_provider import get_provider
    provider = get_provider({"name": "ollama", "provider_type": "ollama",
                             "api_base": "http://localhost:11434",
                             "default_model": "llama3.2"})
    response = await provider.chat(ChatRequest(messages=[...]))
"""
import json
from collections.abc import AsyncGenerator

import httpx

from .openai_compatible import OpenAICompatibleProvider


class OllamaProvider(OpenAICompatibleProvider):
    """
    Ollama: kein API-Key, nutzt OpenAI-kompatibles /v1/-Endpoint.
    Erweitert um native Ollama-Operationen.
    """

    _tier1_core        = ["chat", "chat_stream", "models", "model_detail"]
    _tier2_extended    = []
    _tier3_specialized = []
    _features          = {
        "local":         True,
        "auth_required": False,
        "pull_models":   True,
        "vision":        False,   # modellabhängig
    }

    def _get_endpoint(self, path: str = "") -> str:
        base = self.config.get("api_base", "http://localhost:11434").rstrip("/")
        return f"{base}/v1/chat/completions"

    def _ollama_base(self) -> str:
        return self.config.get("api_base", "http://localhost:11434").rstrip("/")


    def get_models(self) -> list[str]:
        """Config-Modelle — für Live-Liste: await list_local_models()."""
        return self.config.get("models", [self.get_default_model()])

    async def list_local_models(self) -> list[dict]:
        """
        Fragt Ollama nach installierten Modellen.
        Gibt Liste von {name, size, modified_at} zurück.
        """
        await self._ensure_client()
        try:
            resp = await self._client.get(f"{self._ollama_base()}/api/tags")
            resp.raise_for_status()
            return resp.json().get("models", [])
        except Exception as e:
            return [{"error": str(e)}]

    async def pull_model(self, model_name: str) -> AsyncGenerator[str, None]:
        """
        Zieht ein Modell von Ollama-Registry. Streamt Status-Updates.
        Usage: async for status in provider.pull_model("llama3.2"): print(status)
        """
        await self._ensure_client()
        payload = {"name": model_name, "stream": True}
        async with self._client.stream(
            "POST", f"{self._ollama_base()}/api/pull", json=payload
        ) as resp:
            async for line in resp.aiter_lines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        yield data.get("status", line)
                    except json.JSONDecodeError:
                        yield line

    async def delete_model(self, model_name: str) -> bool:
        """Löscht ein lokales Modell."""
        await self._ensure_client()
        try:
            resp = await self._client.request(
                "DELETE", f"{self._ollama_base()}/api/delete",
                json={"name": model_name}
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def is_running(self) -> bool:
        try:
            client = httpx.AsyncClient(timeout=3.0)
            resp   = await client.get(f"{self._ollama_base()}/api/tags")
            await client.aclose()
            return resp.status_code == 200
        except Exception:
            return False
