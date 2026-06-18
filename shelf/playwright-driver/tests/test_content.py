"""Tests for content tools."""
import pytest

from uc_playwright_driver.tools import (
    get_title, get_text, get_all_texts, get_page_content,
    get_html, get_links, get_attribute, get_aria_snapshot,
    get_console_messages, get_page_requests,
)


@pytest.mark.asyncio
async def test_get_title(mock_client):
    assert await get_title(mock_client) == "Mock Title"


@pytest.mark.asyncio
async def test_get_text(mock_client):
    result = await get_text(mock_client, "h1")
    assert result == "mock text"


@pytest.mark.asyncio
async def test_get_all_texts_found(mock_client):
    result = await get_all_texts(mock_client, "p")
    assert "1." in result


@pytest.mark.asyncio
async def test_get_page_content(mock_client):
    result = await get_page_content(mock_client)
    assert "line1" in result or "line2" in result


@pytest.mark.asyncio
async def test_get_html(mock_client):
    result = await get_html(mock_client)
    assert "<div>" in result


@pytest.mark.asyncio
async def test_get_links(mock_client):
    result = await get_links(mock_client)
    assert "Link" in result


@pytest.mark.asyncio
async def test_get_attribute(mock_client):
    result = await get_attribute(mock_client, "a", "href")
    assert result == "(attribute not found)" or result is not None


@pytest.mark.asyncio
async def test_get_aria_snapshot(mock_client):
    result = await get_aria_snapshot(mock_client)
    assert "heading" in result


@pytest.mark.asyncio
async def test_get_console_messages_empty(mock_client):
    result = await get_console_messages(mock_client)
    assert "no console" in result


@pytest.mark.asyncio
async def test_get_page_requests_empty(mock_client):
    result = await get_page_requests(mock_client)
    assert "no requests" in result
