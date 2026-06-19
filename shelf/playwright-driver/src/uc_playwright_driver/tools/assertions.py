"""Web-first, auto-waiting assertions.

These wrap Playwright's ``expect`` API so an agent can *check* state, not just
drive it. Each assertion auto-waits up to ``timeout`` ms for the condition,
returns a short ``PASS: ...`` string on success, and raises ``ToolError`` with
a readable message on failure.

The ``selector`` argument accepts any Playwright locator string, so CSS, text
and role engines all work, e.g. ``"#submit"``, ``"text=Dashboard"`` or
``'role=button[name="Login"]'``.
"""
from __future__ import annotations

import re

from playwright.async_api import expect

from ..client import BrowserClient, ToolError

_DEFAULT_TIMEOUT = 5_000


async def expect_visible(client: BrowserClient, selector: str, timeout: int = _DEFAULT_TIMEOUT) -> str:
    page = await client.get_page()
    try:
        await expect(page.locator(selector)).to_be_visible(timeout=timeout)
    except AssertionError:
        raise ToolError(f"expect_visible FAILED: '{selector}' not visible within {timeout}ms")
    return f"PASS: '{selector}' is visible"


async def expect_hidden(client: BrowserClient, selector: str, timeout: int = _DEFAULT_TIMEOUT) -> str:
    page = await client.get_page()
    try:
        await expect(page.locator(selector)).to_be_hidden(timeout=timeout)
    except AssertionError:
        raise ToolError(f"expect_hidden FAILED: '{selector}' still visible within {timeout}ms")
    return f"PASS: '{selector}' is hidden"


async def expect_text(client: BrowserClient, selector: str, text: str, timeout: int = _DEFAULT_TIMEOUT) -> str:
    page = await client.get_page()
    try:
        await expect(page.locator(selector)).to_contain_text(text, timeout=timeout)
    except AssertionError:
        raise ToolError(f"expect_text FAILED: '{selector}' did not contain '{text}' within {timeout}ms")
    return f"PASS: '{selector}' contains '{text}'"


async def expect_value(client: BrowserClient, selector: str, value: str, timeout: int = _DEFAULT_TIMEOUT) -> str:
    page = await client.get_page()
    try:
        await expect(page.locator(selector)).to_have_value(value, timeout=timeout)
    except AssertionError:
        raise ToolError(f"expect_value FAILED: '{selector}' did not have value '{value}' within {timeout}ms")
    return f"PASS: '{selector}' has value '{value}'"


async def expect_count(client: BrowserClient, selector: str, count: int, timeout: int = _DEFAULT_TIMEOUT) -> str:
    page = await client.get_page()
    try:
        await expect(page.locator(selector)).to_have_count(count, timeout=timeout)
    except AssertionError:
        raise ToolError(f"expect_count FAILED: '{selector}' did not match {count} element(s) within {timeout}ms")
    return f"PASS: '{selector}' matches {count} element(s)"


async def expect_url(client: BrowserClient, contains: str, timeout: int = _DEFAULT_TIMEOUT) -> str:
    page = await client.get_page()
    try:
        await expect(page).to_have_url(re.compile(re.escape(contains)), timeout=timeout)
    except AssertionError:
        raise ToolError(f"expect_url FAILED: url did not contain '{contains}' within {timeout}ms (was {page.url})")
    return f"PASS: url contains '{contains}'"


async def expect_title(client: BrowserClient, contains: str, timeout: int = _DEFAULT_TIMEOUT) -> str:
    page = await client.get_page()
    try:
        await expect(page).to_have_title(re.compile(re.escape(contains)), timeout=timeout)
    except AssertionError:
        raise ToolError(f"expect_title FAILED: title did not contain '{contains}' within {timeout}ms")
    return f"PASS: title contains '{contains}'"
