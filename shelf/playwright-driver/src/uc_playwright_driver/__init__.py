"""uc-playwright-driver — a plain Playwright driver: navigation, interaction,
content, locators, frames, tabs, storage, network, scripting.

No MCP, no server framework. Just a BrowserClient and a flat set of tool
functions that take the client as first argument.
"""
from .client import BrowserClient, ToolError

__all__ = ["BrowserClient", "ToolError"]
