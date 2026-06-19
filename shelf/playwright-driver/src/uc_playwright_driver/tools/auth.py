"""Authentication primitives.

These take resolved credential *values* (so plain scripts can call them after
reading uc_credentials). They never echo the secret: return strings are redacted.
The agent path resolves the handle in the tool layer and calls these, so the
model only ever supplies a profile name.
"""
from __future__ import annotations

from ..client import BrowserClient


def _locate(page, spec: str):
    """Resolve a field spec to a Playwright locator.

    ``label=...`` and ``placeholder=...`` use the accessibility getters; anything
    else is handed to ``page.locator()`` (CSS, ``role=``, ``text=``, ``xpath=`` …).
    """
    if spec.startswith("label="):
        return page.get_by_label(spec[len("label="):])
    if spec.startswith("placeholder="):
        return page.get_by_placeholder(spec[len("placeholder="):])
    return page.locator(spec)


async def set_basic_auth(client: BrowserClient, username: str, password: str) -> str:
    """Set HTTP Basic-Auth on the browser context (takes effect on next open)."""
    await client.set_http_credentials(username, password)
    return "Basic-Auth aktiv (Zugangsdaten verborgen)"


async def login_form(
    client: BrowserClient,
    username: str,
    password: str,
    user_field: str,
    pass_field: str,
    submit: str,
    url: str = "",
) -> str:
    """Fill a username/password form and submit it.

    Field specs follow ``_locate`` (label=/placeholder=/selector). With ``url``
    the page is opened first. The values are never echoed back.
    """
    page = await client.get_page()
    if url:
        await page.goto(url)
    await _locate(page, user_field).fill(username)
    await _locate(page, pass_field).fill(password)
    await _locate(page, submit).click()
    await page.wait_for_load_state("domcontentloaded")
    return "Form-Login ausgefuehrt (Zugangsdaten verborgen)"
