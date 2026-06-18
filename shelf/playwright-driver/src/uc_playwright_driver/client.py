"""BrowserClient — Playwright browser lifecycle, Multi-Tab."""
from __future__ import annotations

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)


class ToolError(Exception):
    """Raised by tools on recoverable errors."""


class BrowserClient:
    """Playwright browser lifecycle manager with multi-tab support."""

    def __init__(self, config: dict) -> None:
        self._headless:      bool = config.get("headless",     True)
        self._timeout:       int  = config.get("timeout",      30_000)
        self._browser_type:  str  = config.get("browser_type", "chromium")
        self._slow_mo:       int  = config.get("slow_mo",      0)

        self._playwright: Playwright    | None = None
        self._browser:    Browser       | None = None
        self._context:    BrowserContext| None = None

        self._pages:      dict[int, Page] = {}
        self._active_tab: int             = 0
        self._next_id:    int             = 0
        self._frame_selector: str | None  = None


    async def _ensure_context(self) -> BrowserContext:
        if self._context is None:
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            launcher = getattr(self._playwright, self._browser_type)
            self._browser = await launcher.launch(
                headless=self._headless,
                slow_mo=self._slow_mo,
            )
            self._context = await self._browser.new_context()
        return self._context

    async def cleanup(self) -> None:
        for page in list(self._pages.values()):
            if not page.is_closed():
                await page.close()
        self._pages.clear()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._context        = None
        self._browser        = None
        self._playwright     = None
        self._active_tab     = 0
        self._next_id        = 0
        self._frame_selector = None

    async def relaunch(
        self,
        headless:     bool | None = None,
        browser_type: str  | None = None,
    ) -> None:
        if headless is not None:
            self._headless = headless
        if browser_type is not None:
            if browser_type not in ("chromium", "firefox", "webkit"):
                raise ToolError(f"Unknown browser '{browser_type}'. Use chromium, firefox, or webkit.")
            self._browser_type = browser_type
        await self.cleanup()


    async def get_page(self, tab_id: int | None = None) -> Page:
        """Return page for tab_id (default: active tab). Creates first tab lazily."""
        tid = self._active_tab if tab_id is None else tab_id

        if tid not in self._pages or self._pages[tid].is_closed():
            ctx = await self._ensure_context()
            page = await ctx.new_page()
            page.set_default_timeout(self._timeout)
            if tid not in self._pages:
                self._pages[tid] = page
                self._next_id    = max(self._next_id, tid + 1)
            else:
                self._pages[tid] = page

        return self._pages[tid]

    async def new_tab(self) -> int:
        ctx  = await self._ensure_context()
        page = await ctx.new_page()
        page.set_default_timeout(self._timeout)
        tid  = self._next_id
        self._pages[tid]  = page
        self._active_tab  = tid
        self._next_id    += 1
        return tid

    def switch_tab(self, tab_id: int) -> None:
        if tab_id not in self._pages:
            raise ToolError(f"Tab {tab_id} does not exist. Available: {self.list_tabs()}")
        self._active_tab = tab_id

    async def close_tab(self, tab_id: int) -> None:
        if tab_id not in self._pages:
            raise ToolError(f"Tab {tab_id} does not exist.")
        page = self._pages.pop(tab_id)
        if not page.is_closed():
            await page.close()
        if self._active_tab == tab_id:
            self._active_tab = next(iter(self._pages), 0)

    def list_tabs(self) -> list[int]:
        return sorted(self._pages.keys())


    @property
    def headless(self) -> bool:
        return self._headless

    @property
    def browser_type(self) -> str:
        return self._browser_type

    @property
    def timeout(self) -> int:
        return self._timeout

    @property
    def active_tab(self) -> int:
        return self._active_tab
