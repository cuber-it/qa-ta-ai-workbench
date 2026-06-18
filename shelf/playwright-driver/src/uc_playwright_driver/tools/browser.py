"""Browser, viewport, screenshot, and recording tools."""
from __future__ import annotations

import base64
from pathlib import Path

from ..client import BrowserClient


async def screenshot(client: BrowserClient, path: str = "", full_page: bool = False) -> str:
    """Take a screenshot. Returns base64 if no path given, else saves to file."""
    page = await client.get_page()
    if path:
        fp = Path(path).resolve()
        fp.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(fp), full_page=full_page)
        return f"Screenshot saved: {fp}"
    buf = await page.screenshot(full_page=full_page)
    return base64.b64encode(buf).decode()


async def screenshot_element(client: BrowserClient, selector: str, path: str = "") -> str:
    page = await client.get_page()
    loc  = page.locator(selector)
    await loc.wait_for(timeout=5000)
    if path:
        fp = Path(path).resolve()
        fp.parent.mkdir(parents=True, exist_ok=True)
        await loc.screenshot(path=str(fp))
        return f"Element screenshot saved: {fp}"
    buf = await loc.screenshot()
    return base64.b64encode(buf).decode()


async def wait_for(client: BrowserClient, selector: str, timeout: int = 10000) -> str:
    page = await client.get_page()
    await page.wait_for_selector(selector, timeout=timeout)
    return f"Found: {selector}"


async def wait_for_hidden(client: BrowserClient, selector: str, timeout: int = 10000) -> str:
    page = await client.get_page()
    await page.wait_for_selector(selector, state="hidden", timeout=timeout)
    return f"Hidden: {selector}"


async def wait_for_url(client: BrowserClient, url_pattern: str, timeout: int = 10000) -> str:
    page = await client.get_page()
    await page.wait_for_url(url_pattern, timeout=timeout)
    return f"URL reached: {page.url}"


async def set_viewport(client: BrowserClient, width: int, height: int) -> str:
    page = await client.get_page()
    await page.set_viewport_size({"width": width, "height": height})
    return f"Viewport: {width}x{height}"


async def scroll_to(client: BrowserClient, selector: str) -> str:
    page = await client.get_page()
    await page.locator(selector).scroll_into_view_if_needed()
    return f"Scrolled to: {selector}"


async def scroll_page(client: BrowserClient, direction: str = "down", amount: int = 500) -> str:
    page = await client.get_page()
    match direction:
        case "top":
            await page.evaluate("window.scrollTo(0, 0)")
        case "bottom":
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        case "up":
            await page.evaluate(f"window.scrollBy(0, -{amount})")
        case _:
            await page.evaluate(f"window.scrollBy(0, {amount})")
    return f"Scrolled: {direction}"


async def set_headless(client: BrowserClient, headless: bool) -> str:
    await client.relaunch(headless=headless)
    mode = "headless" if headless else "headed"
    return f"Browser restarted in {mode} mode."


async def set_browser(client: BrowserClient, browser_type: str) -> str:
    await client.relaunch(browser_type=browser_type)
    return f"Browser switched to {browser_type}."


async def start_recording(client: BrowserClient, path: str = "recording.webm") -> str:
    """Start video recording via page.screencast (Playwright v1.59+)."""
    page = await client.get_page()
    fp   = Path(path).resolve()
    fp.parent.mkdir(parents=True, exist_ok=True)
    await page.screencast.start(path=str(fp))
    return f"Recording started: {fp}"


async def stop_recording(client: BrowserClient) -> str:
    """Stop video recording and save the file."""
    page = await client.get_page()
    await page.screencast.stop()
    return "Recording stopped."


async def recording_show_actions(
    client: BrowserClient,
    position: str = "top-right",
) -> str:
    """Annotate recording with action highlights."""
    page = await client.get_page()
    await page.screencast.show_actions(position=position)
    return f"Action annotations enabled ({position})."
