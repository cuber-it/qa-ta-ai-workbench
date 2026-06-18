"""
Provider Registry — Thread-safe Hot-Swap.
"""
import asyncio
from typing import Optional

from ..core.base import BaseProvider
from ..factory import get_provider


class ProviderRegistry:
    """Singleton — hält den aktiven Provider und ermöglicht Hot-Swap."""

    def __init__(self):
        self._provider: Optional[BaseProvider] = None
        self._lock = asyncio.Lock()

    def get(self) -> Optional[BaseProvider]:
        return self._provider

    def set_sync(self, config: dict) -> BaseProvider:
        """Synchron setzen (beim Start)."""
        self._provider = get_provider(config)
        return self._provider

    async def swap(self, config: dict) -> BaseProvider:
        """Hot-Swap im laufenden Betrieb."""
        async with self._lock:
            self._provider = get_provider(config)
            return self._provider

    def info(self) -> dict:
        if self._provider is None:
            return {"status": "no_provider"}
        return {
            "provider":      self._provider.provider_name,
            "model":         self._provider.get_default_model(),
            "capabilities":  self._provider.get_capabilities().model_dump(),
        }


# Modul-level Singleton
registry = ProviderRegistry()
