"""Network interception and monitoring tools."""
from __future__ import annotations


from ..client import BrowserClient


async def mock_route(
    client: BrowserClient,
    url_pattern: str,
    status: int = 200,
    body: str = "{}",
    content_type: str = "application/json",
) -> str:
    """Mock all requests matching url_pattern with a fixed response."""
    page = await client.get_page()

    async def handler(route):
        await route.fulfill(
            status=status,
            content_type=content_type,
            body=body,
        )

    await page.route(url_pattern, handler)
    return f"Route mocked: {url_pattern} → {status}"


async def clear_route(client: BrowserClient, url_pattern: str) -> str:
    """Remove a previously registered route mock."""
    page = await client.get_page()
    await page.unroute(url_pattern)
    return f"Route cleared: {url_pattern}"


async def wait_for_response(
    client: BrowserClient,
    url_pattern: str,
    timeout: int = 10000,
) -> str:
    """Wait for a network response matching url_pattern."""
    page = await client.get_page()
    async with page.expect_response(url_pattern, timeout=timeout) as resp_info:
        pass
    response = await resp_info.value
    return f"Response: {response.status} {response.url[:100]}"


async def abort_route(client: BrowserClient, url_pattern: str) -> str:
    """Block all requests matching url_pattern."""
    page = await client.get_page()
    await page.route(url_pattern, lambda route: route.abort())
    return f"Route blocked: {url_pattern}"
