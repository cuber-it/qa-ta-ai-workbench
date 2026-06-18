"""Test fixtures — MockPage and MockBrowserClient."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from uc_playwright_driver.client import BrowserClient


class MockLocator:
    def __init__(self, text="mock text", count=1, attribute=None):
        self._text      = text
        self._count     = count
        self._attribute = attribute

    async def inner_text(self): return self._text
    async def inner_html(self):  return f"<div>{self._text}</div>"
    async def count(self):       return self._count
    async def wait_for(self, **kw): pass
    async def click(self, **kw): pass
    async def dblclick(self, **kw): pass
    async def fill(self, text, **kw): pass
    async def press(self, key): pass
    async def check(self, **kw): pass
    async def uncheck(self, **kw): pass
    async def hover(self, **kw): pass
    async def focus(self, **kw): pass
    async def clear(self, **kw): pass
    async def screenshot(self, **kw): return b"PNG"
    async def scroll_into_view_if_needed(self): pass
    async def select_option(self, value=None, label=None, **kw): pass
    async def set_input_files(self, path): pass
    async def get_attribute(self, attr): return self._attribute
    async def aria_snapshot(self): return "- heading: mock"
    async def drag_to(self, target): pass
    async def evaluate(self, expr): return {"tag": "div", "role": "", "text": self._text,
        "id": "", "classes": "", "type": "", "name": "", "value": "",
        "href": "", "placeholder": "", "ariaLabel": "", "testId": "",
        "visible": True, "enabled": True}

    @property
    def first(self): return self
    def nth(self, n): return self


class MockPage:
    def __init__(self):
        self.url = "https://example.com"

    async def goto(self, url, **kw):    self.url = url
    async def go_back(self, **kw):      return MagicMock()
    async def go_forward(self, **kw):   return MagicMock()
    async def reload(self, **kw):       pass
    async def title(self):              return "Mock Title"
    async def inner_text(self, sel):    return "line1\nline2"
    async def inner_html(self, sel):    return "<html/>"
    async def content(self):            return "<html/>"
    async def screenshot(self, **kw):   return b"PNG"
    async def set_viewport_size(self, size): pass
    async def evaluate(self, code, *a): return "result"
    async def wait_for_selector(self, sel, **kw): pass
    async def wait_for_url(self, pat, **kw): pass
    async def wait_for_load_state(self, state="load"): pass
    async def route(self, pattern, handler): pass
    async def unroute(self, pattern): pass
    async def close(self): pass

    def locator(self, sel): return MockLocator()
    def get_by_role(self, role, **kw): return MockLocator()
    def get_by_text(self, text, **kw): return MockLocator()
    def get_by_label(self, label): return MockLocator()
    def get_by_placeholder(self, ph): return MockLocator()
    def get_by_test_id(self, tid): return MockLocator()
    def frame_locator(self, sel): return MockLocator()

    def is_closed(self): return False
    def set_default_timeout(self, ms): pass
    def once(self, event, handler): pass
    def console_messages(self): return []
    def requests(self): return []

    async def eval_on_selector_all(self, sel, expr):
        return [{"text": "Link", "href": "https://example.com"}]


@pytest.fixture
def mock_page():
    return MockPage()


@pytest.fixture
def mock_client(mock_page):
    client = BrowserClient({})
    client._pages     = {0: mock_page}
    client._active_tab = 0
    client._next_id    = 1
    return client
