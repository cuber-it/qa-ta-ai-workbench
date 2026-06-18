"""test_server.py — FastAPI endpoints mit MockProvider + Hot-Swap."""
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from uc_llm_provider.server.registry import ProviderRegistry
from uc_llm_provider.server.routes import (
    chat_router,
    health_router,
    models_router,
    provider_router,
    tokens_router,
)


@pytest.fixture
def test_registry(mock_provider):
    reg = ProviderRegistry()
    reg._provider = mock_provider
    return reg


@pytest.fixture
def test_app(mock_provider, monkeypatch):
    # Registry patchen
    reg = ProviderRegistry()
    reg._provider = mock_provider

    import uc_llm_provider.server.routes.chat as chat_mod
    import uc_llm_provider.server.routes.health as health_mod
    import uc_llm_provider.server.routes.provider as prov_mod
    import uc_llm_provider.server.routes.tokens as tokens_mod

    monkeypatch.setattr(health_mod, "registry", reg)
    monkeypatch.setattr(chat_mod,   "registry", reg)
    monkeypatch.setattr(tokens_mod, "registry", reg)
    monkeypatch.setattr(prov_mod,   "registry", reg)

    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(health_router,   prefix="/v1")
    app.include_router(chat_router,     prefix="/v1")
    app.include_router(models_router,   prefix="/v1")
    app.include_router(tokens_router,   prefix="/v1")
    app.include_router(provider_router, prefix="/v1")
    return TestClient(app)


def test_health(test_app):
    r = test_app.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["provider"] == "mock"


def test_capabilities(test_app):
    r = test_app.get("/v1/capabilities")
    assert r.status_code == 200
    assert "chat" in r.json()["tier1"]


def test_models(test_app):
    r = test_app.get("/v1/models")
    assert r.status_code == 200
    assert "data" in r.json()


def test_chat(test_app):
    r = test_app.post("/v1/chat", json={
        "model": "mock-model",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 100,
    })
    assert r.status_code == 200
    data = r.json()
    assert "content" in data
    assert data["content"][0]["text"] == "mock response"


def test_tokens_count(test_app):
    r = test_app.post("/v1/tokens/count", json={
        "messages": [{"role": "user", "content": "Hello world"}],
        "model": "mock-model",
    })
    assert r.status_code == 200
    assert "input_tokens" in r.json()


def test_get_provider(test_app):
    r = test_app.get("/v1/provider")
    assert r.status_code == 200
    assert r.json()["provider"] == "mock"
