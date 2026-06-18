"""
uc-llm-provider Server — FastAPI App
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import ServerConfig
from .registry import registry
from .routes import chat_router, health_router, models_router, provider_router, tokens_router


def create_app(config: ServerConfig) -> FastAPI:

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        registry.set_sync(config.to_provider_config())
        yield

    app = FastAPI(
        title="uc-llm-provider Server",
        description="Unified LLM API — Anthropic, OpenAI, Google, Ollama and more",
        version="0.5.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router,    prefix="/v1", tags=["health"])
    app.include_router(chat_router,      prefix="/v1", tags=["chat"])
    app.include_router(models_router,    prefix="/v1", tags=["models"])
    app.include_router(tokens_router,    prefix="/v1", tags=["tokens"])
    app.include_router(provider_router,  prefix="/v1", tags=["provider"])

    return app
