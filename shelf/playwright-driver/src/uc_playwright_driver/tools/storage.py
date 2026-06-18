"""Cookies and local storage tools."""
from __future__ import annotations

import json

from ..client import BrowserClient


async def get_cookies(client: BrowserClient) -> str:
    page    = await client.get_page()
    cookies = await page.context.cookies()
    if not cookies:
        return "(no cookies)"
    return "\n".join(
        f"{c['name']}={c['value'][:60]} (domain={c['domain']})"
        for c in cookies
    )


async def set_cookie(
    client: BrowserClient,
    name: str,
    value: str,
    domain: str = "",
    path: str = "/",
) -> str:
    page   = await client.get_page()
    cookie = {"name": name, "value": value, "path": path}
    if domain:
        cookie["domain"] = domain
    else:
        cookie["url"] = page.url or "http://localhost"
    await page.context.add_cookies([cookie])
    return f"Cookie set: {name}"


async def clear_cookies(client: BrowserClient) -> str:
    page = await client.get_page()
    await page.context.clear_cookies()
    return "Cookies cleared"


async def get_local_storage(client: BrowserClient, key: str = "") -> str:
    page = await client.get_page()
    if key:
        value = await page.evaluate(f"localStorage.getItem({json.dumps(key)})")
        return value if value is not None else f"(key '{key}' not found)"
    items = await page.evaluate(
        "Object.entries(localStorage).map(([k, v]) => k + '=' + v.substring(0, 80))"
    )
    return "\n".join(items) if items else "(localStorage empty)"


async def set_local_storage(client: BrowserClient, key: str, value: str) -> str:
    page = await client.get_page()
    await page.evaluate(
        f"localStorage.setItem({json.dumps(key)}, {json.dumps(value)})"
    )
    return f"localStorage[{key}] set"


async def clear_storage(client: BrowserClient) -> str:
    page = await client.get_page()
    await page.evaluate("localStorage.clear(); sessionStorage.clear()")
    return "localStorage and sessionStorage cleared"
