"""iFrame switching tools."""
from __future__ import annotations

from ..client import BrowserClient


async def switch_to_frame(client: BrowserClient, selector: str) -> str:
    await client.get_page()
    client._frame_selector = selector
    return f"Switched to frame: {selector}"


async def switch_to_main(client: BrowserClient) -> str:
    client._frame_selector = None
    return "Switched back to main frame"
