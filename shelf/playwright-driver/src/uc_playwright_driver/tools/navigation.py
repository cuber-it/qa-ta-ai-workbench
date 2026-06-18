"""Navigation tools."""
from __future__ import annotations

from ..client import BrowserClient, ToolError


async def navigate(client: BrowserClient, url: str, wait_until: str = "domcontentloaded") -> str:
    page = await client.get_page()
    await page.goto(url, wait_until=wait_until)
    return f"Navigated: {page.url}"


async def current_url(client: BrowserClient) -> str:
    page = await client.get_page()
    return page.url


async def go_back(client: BrowserClient) -> str:
    page = await client.get_page()
    response = await page.go_back(wait_until="domcontentloaded")
    if response is None:
        raise ToolError("No previous page in history.")
    return f"Back: {page.url}"


async def go_forward(client: BrowserClient) -> str:
    page = await client.get_page()
    response = await page.go_forward(wait_until="domcontentloaded")
    if response is None:
        raise ToolError("No next page in history.")
    return f"Forward: {page.url}"


async def reload(client: BrowserClient) -> str:
    page = await client.get_page()
    await page.reload(wait_until="domcontentloaded")
    return f"Reloaded: {page.url}"
