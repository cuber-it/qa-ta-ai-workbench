"""Multi-tab management tools."""
from __future__ import annotations

from ..client import BrowserClient


async def new_tab(client: BrowserClient) -> str:
    tab_id = await client.new_tab()
    return f"New tab opened: {tab_id}"


async def list_tabs(client: BrowserClient) -> str:
    tabs   = client.list_tabs()
    active = client.active_tab
    lines  = [f"{'*' if t == active else ' '} Tab {t}" for t in tabs]
    return "\n".join(lines) if lines else "(no tabs)"


async def switch_tab(client: BrowserClient, tab_id: int) -> str:
    client.switch_tab(tab_id)
    return f"Switched to tab {tab_id}"


async def close_tab(client: BrowserClient, tab_id: int) -> str:
    await client.close_tab(tab_id)
    return f"Closed tab {tab_id}"
