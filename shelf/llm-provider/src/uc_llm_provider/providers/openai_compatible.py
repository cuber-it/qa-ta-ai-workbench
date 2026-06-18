"""
OpenAI-Compatible Provider — Basis für lokale und kompatible Endpoints.

Ollama, LM Studio, llama.cpp-server, vLLM, LocalAI sprechen alle
das OpenAI-API-Format. Dieser Provider konfiguriert nur api_base
und api_key (optional).

Config (YAML):
    name: lm-studio
    provider_type: openai_compatible
    api_base: http://localhost:1234/v1
    api_key: ""               # leer = kein Auth
    default_model: local-model
    models:
      - local-model
"""
from .openai import OpenAIProvider


class OpenAICompatibleProvider(OpenAIProvider):
    """
    Thin wrapper um OpenAIProvider — überschreibt nur Endpoint und Auth.
    api_key ist optional; wenn leer, wird kein Authorization-Header gesetzt.
    """

    _tier1_core        = ["chat", "chat_stream", "models"]
    _tier2_extended    = []
    _tier3_specialized = []
    _features          = {"local": True, "auth_required": False}

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        key = self.config.get("api_key", "").strip()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def _get_endpoint(self, path: str = "") -> str:
        base = self.config.get("api_base", "http://localhost:11434/v1").rstrip("/")
        return f"{base}/chat/completions"
