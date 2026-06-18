"""Tests for navigation tools."""
import pytest

from uc_playwright_driver.client import ToolError
from uc_playwright_driver.tools import navigate, current_url, go_back, go_forward, reload


@pytest.mark.asyncio
async def test_navigate(mock_client):
    result = await navigate(mock_client, "https://test.com")
    assert "https://test.com" in result


@pytest.mark.asyncio
async def test_current_url(mock_client):
    result = await current_url(mock_client)
    assert result == "https://example.com"


@pytest.mark.asyncio
async def test_go_back(mock_client):
    result = await go_back(mock_client)
    assert "Back" in result


@pytest.mark.asyncio
async def test_go_back_no_history(mock_client, mock_page):
    mock_page.go_back = lambda **kw: _async_none()
    result_coro = go_back(mock_client)
    with pytest.raises(ToolError):
        await result_coro


@pytest.mark.asyncio
async def test_go_forward(mock_client):
    result = await go_forward(mock_client)
    assert "Forward" in result


@pytest.mark.asyncio
async def test_reload(mock_client):
    result = await reload(mock_client)
    assert "Reloaded" in result


async def _async_none():
    return None
