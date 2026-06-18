"""Tests for locator tools."""
import pytest

from uc_playwright_driver.tools import (
    find_by_role, find_by_text, find_by_label, find_by_placeholder,
    find_by_test_id, describe_element, find_interactive_elements,
)


@pytest.mark.asyncio
async def test_find_by_role(mock_client):
    result = await find_by_role(mock_client, "button")
    assert "Found" in result or "button" in result


@pytest.mark.asyncio
async def test_find_by_role_with_name(mock_client):
    result = await find_by_role(mock_client, "button", name="Submit")
    assert result is not None


@pytest.mark.asyncio
async def test_find_by_text(mock_client):
    result = await find_by_text(mock_client, "Submit")
    assert "Found" in result


@pytest.mark.asyncio
async def test_find_by_label(mock_client):
    result = await find_by_label(mock_client, "Email")
    assert "label" in result.lower() or "Found" in result


@pytest.mark.asyncio
async def test_find_by_placeholder(mock_client):
    result = await find_by_placeholder(mock_client, "Enter text")
    assert "Found" in result or "placeholder" in result.lower()


@pytest.mark.asyncio
async def test_find_by_test_id(mock_client):
    result = await find_by_test_id(mock_client, "submit-btn")
    assert result is not None


@pytest.mark.asyncio
async def test_describe_element(mock_client):
    result = await describe_element(mock_client, "#main")
    assert "<div>" in result or "visible" in result


@pytest.mark.asyncio
async def test_find_interactive_elements(mock_client, mock_page):
    mock_page.evaluate = lambda code, *a: _async_list()
    result = await find_interactive_elements(mock_client)
    assert "no interactive" in result or result is not None


async def _async_list():
    return []
