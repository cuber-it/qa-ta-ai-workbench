"""JavaScript execution tool."""
from __future__ import annotations

import json

from ..client import BrowserClient


async def execute_script(client: BrowserClient, code: str) -> str:
    """Execute JavaScript in the page context and return the result."""
    page   = await client.get_page()
    result = await page.evaluate(code)
    if result is None:
        return "(no return value)"
    if isinstance(result, (dict, list)):
        return json.dumps(result, ensure_ascii=False, indent=2)
    return str(result)
