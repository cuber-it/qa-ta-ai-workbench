"""Tests for BrowserClient multi-tab management."""
import pytest

from uc_playwright_driver.client import ToolError


@pytest.mark.asyncio
async def test_new_tab(mock_client):
    tab_id = await mock_client.new_tab()
    # new_tab creates a real page — skip in unit test, verify tab tracking
    assert isinstance(tab_id, int)


def test_list_tabs(mock_client):
    tabs = mock_client.list_tabs()
    assert 0 in tabs


def test_switch_tab(mock_client, mock_page):
    mock_client._pages[1]  = mock_page
    mock_client._next_id   = 2
    mock_client.switch_tab(1)
    assert mock_client.active_tab == 1


def test_switch_tab_invalid(mock_client):
    with pytest.raises(ToolError):
        mock_client.switch_tab(99)


@pytest.mark.asyncio
async def test_close_tab(mock_client, mock_page):
    mock_client._pages[1] = mock_page
    mock_client._next_id  = 2
    await mock_client.close_tab(1)
    assert 1 not in mock_client.list_tabs()


@pytest.mark.asyncio
async def test_close_active_tab_switches(mock_client, mock_page):
    mock_client._pages[1]  = mock_page
    mock_client._active_tab = 1
    mock_client._next_id    = 2
    await mock_client.close_tab(1)
    assert mock_client.active_tab == 0


async def test_relaunch_invalid_browser(mock_client):
    with pytest.raises(ToolError):
        await mock_client.relaunch(browser_type="ie6")
