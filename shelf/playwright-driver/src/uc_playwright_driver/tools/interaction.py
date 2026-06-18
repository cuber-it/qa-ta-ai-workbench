"""Interaction tools."""
from __future__ import annotations

from ..client import BrowserClient


async def click(client: BrowserClient, selector: str) -> str:
    page = await client.get_page()
    await page.locator(selector).click(timeout=5000)
    await page.wait_for_load_state("domcontentloaded")
    return f"Clicked: {selector}"


async def double_click(client: BrowserClient, selector: str) -> str:
    page = await client.get_page()
    await page.locator(selector).dblclick(timeout=5000)
    return f"Double-clicked: {selector}"


async def right_click(client: BrowserClient, selector: str) -> str:
    page = await client.get_page()
    await page.locator(selector).click(button="right", timeout=5000)
    return f"Right-clicked: {selector}"


async def fill(client: BrowserClient, selector: str, text: str) -> str:
    page = await client.get_page()
    await page.locator(selector).fill(text, timeout=5000)
    return f"Filled: {selector}"


async def type_text(client: BrowserClient, selector: str, text: str, delay: int = 50) -> str:
    """Type character by character — useful for autocomplete fields."""
    page = await client.get_page()
    await page.locator(selector).press_sequentially(text, delay=delay)
    return f"Typed into: {selector}"


async def press(client: BrowserClient, key: str, selector: str = "") -> str:
    """Press a key. If selector given: press on that element, else keyboard-global."""
    page = await client.get_page()
    if selector:
        await page.locator(selector).press(key)
        return f"Pressed {key} on: {selector}"
    await page.keyboard.press(key)
    return f"Pressed: {key}"


async def select_option(client: BrowserClient, selector: str, value: str) -> str:
    page = await client.get_page()
    await page.locator(selector).select_option(value, timeout=5000)
    return f"Selected value '{value}' in {selector}"


async def select_option_by_text(client: BrowserClient, selector: str, text: str) -> str:
    page = await client.get_page()
    await page.locator(selector).select_option(label=text, timeout=5000)
    return f"Selected '{text}' in {selector}"


async def check(client: BrowserClient, selector: str) -> str:
    page = await client.get_page()
    await page.locator(selector).check(timeout=5000)
    return f"Checked: {selector}"


async def uncheck(client: BrowserClient, selector: str) -> str:
    page = await client.get_page()
    await page.locator(selector).uncheck(timeout=5000)
    return f"Unchecked: {selector}"


async def hover(client: BrowserClient, selector: str) -> str:
    page = await client.get_page()
    await page.locator(selector).hover(timeout=5000)
    return f"Hovered: {selector}"


async def focus(client: BrowserClient, selector: str) -> str:
    page = await client.get_page()
    await page.locator(selector).focus(timeout=5000)
    return f"Focused: {selector}"


async def clear(client: BrowserClient, selector: str) -> str:
    page = await client.get_page()
    await page.locator(selector).clear(timeout=5000)
    return f"Cleared: {selector}"


async def drag_and_drop(client: BrowserClient, source: str, target: str) -> str:
    page = await client.get_page()
    await page.locator(source).drag_to(page.locator(target))
    return f"Dragged {source} → {target}"


async def upload_file(client: BrowserClient, selector: str, path: str) -> str:
    page = await client.get_page()
    await page.locator(selector).set_input_files(path)
    return f"Uploaded file to: {selector}"


async def wait_for_download(client: BrowserClient, trigger_selector: str = "") -> str:
    """Click trigger_selector and wait for download. Returns downloaded file path."""
    page = await client.get_page()
    async with page.expect_download() as dl_info:
        if trigger_selector:
            await page.locator(trigger_selector).click()
    download = await dl_info.value
    path     = await download.path()
    return f"Downloaded: {download.suggested_filename} → {path}"


async def accept_dialog(client: BrowserClient) -> str:
    """Accept the next browser dialog (alert/confirm/prompt)."""
    page = await client.get_page()

    async def handler(dialog):
        await dialog.accept()

    page.once("dialog", handler)
    return "Dialog handler set: will accept next dialog"


async def dismiss_dialog(client: BrowserClient) -> str:
    """Dismiss the next browser dialog."""
    page = await client.get_page()

    async def handler(dialog):
        await dialog.dismiss()

    page.once("dialog", handler)
    return "Dialog handler set: will dismiss next dialog"
