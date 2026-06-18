"""Semantic locator tools."""
from __future__ import annotations

from ..client import BrowserClient


async def find_by_role(client: BrowserClient, role: str, name: str = "") -> str:
    page   = await client.get_page()
    kwargs = {"name": name} if name else {}
    loc    = page.get_by_role(role, **kwargs)
    count  = await loc.count()
    if count == 0:
        return f"(no elements with role '{role}' found)"
    texts = []
    for i in range(min(count, 20)):
        texts.append(f"{i + 1}. {(await loc.nth(i).inner_text()).strip()[:80]}")
    return f"Found {count} element(s) with role '{role}':\n" + "\n".join(texts)


async def find_by_text(client: BrowserClient, text: str, exact: bool = False) -> str:
    page  = await client.get_page()
    loc   = page.get_by_text(text, exact=exact)
    count = await loc.count()
    if count == 0:
        return f"(no elements with text '{text}')"
    results = []
    for i in range(min(count, 10)):
        el    = loc.nth(i)
        tag   = await el.evaluate("e => e.tagName.toLowerCase()")
        inner = (await el.inner_text())[:80]
        results.append(f"{i + 1}. <{tag}> {inner}")
    return f"Found {count} element(s):\n" + "\n".join(results)


async def find_by_label(client: BrowserClient, label: str) -> str:
    page  = await client.get_page()
    loc   = page.get_by_label(label)
    count = await loc.count()
    if count == 0:
        return f"(no input with label '{label}')"
    tag = await loc.first.evaluate("e => e.tagName.toLowerCase() + '[type=' + (e.type||'') + ']'")
    return f"Found input with label '{label}': <{tag}>"


async def find_by_placeholder(client: BrowserClient, placeholder: str) -> str:
    page  = await client.get_page()
    loc   = page.get_by_placeholder(placeholder)
    count = await loc.count()
    if count == 0:
        return f"(no input with placeholder '{placeholder}')"
    return f"Found {count} input(s) with placeholder '{placeholder}'"


async def find_by_test_id(client: BrowserClient, test_id: str) -> str:
    page  = await client.get_page()
    loc   = page.get_by_test_id(test_id)
    count = await loc.count()
    if count == 0:
        return f"(no element with test-id '{test_id}')"
    tag  = await loc.first.evaluate("e => e.tagName.toLowerCase()")
    text = (await loc.first.inner_text())[:80]
    return f"Found <{tag}> with test-id '{test_id}': {text}"


async def click_by_role(client: BrowserClient, role: str, name: str = "") -> str:
    page   = await client.get_page()
    kwargs = {"name": name} if name else {}
    await page.get_by_role(role, **kwargs).click()
    await page.wait_for_load_state("domcontentloaded")
    label = f"role={role}" + (f", name='{name}'" if name else "")
    return f"Clicked: {label}"


async def click_by_text(client: BrowserClient, text: str) -> str:
    page = await client.get_page()
    await page.get_by_text(text).click()
    await page.wait_for_load_state("domcontentloaded")
    return f"Clicked text: '{text}'"


async def fill_by_label(client: BrowserClient, label: str, value: str) -> str:
    page = await client.get_page()
    await page.get_by_label(label).fill(value)
    return f"Filled '{label}': {value}"


async def describe_element(client: BrowserClient, selector: str) -> str:
    page = await client.get_page()
    loc  = page.locator(selector)
    await loc.wait_for(timeout=5000)
    info = await loc.evaluate("""e => ({
        tag: e.tagName.toLowerCase(),
        role: e.getAttribute('role') || '',
        text: (e.innerText || '').substring(0, 100),
        id: e.id || '',
        classes: e.className || '',
        type: e.type || '',
        name: e.name || '',
        value: e.value || '',
        href: e.href || '',
        placeholder: e.placeholder || '',
        ariaLabel: e.getAttribute('aria-label') || '',
        testId: e.getAttribute('data-testid') || '',
        visible: e.offsetParent !== null,
        enabled: !e.disabled,
    })""")
    lines = [f"<{info['tag']}>"]
    for key in ["role", "id", "classes", "type", "name",
                "text", "value", "href", "placeholder", "ariaLabel", "testId"]:
        if info.get(key):
            lines.append(f"  {key}: {info[key]}")
    lines.append(f"  visible: {info['visible']}, enabled: {info['enabled']}")
    return "\n".join(lines)


async def find_interactive_elements(client: BrowserClient) -> str:
    page     = await client.get_page()
    elements = await page.evaluate("""() => {
        const sel = 'a, button, input, select, textarea, [role="button"], [role="link"], [onclick]';
        return Array.from(document.querySelectorAll(sel)).slice(0, 50).map(e => ({
            tag:    e.tagName.toLowerCase(),
            type:   e.type || '',
            text:   (e.innerText || e.value || e.placeholder
                     || e.getAttribute('aria-label') || '').substring(0, 60).trim(),
            id:     e.id || '',
            name:   e.name || '',
            role:   e.getAttribute('role') || '',
            testId: e.getAttribute('data-testid') || '',
            href:   e.tagName === 'A' ? e.href : '',
        }));
    }""")
    if not elements:
        return "(no interactive elements found)"
    lines = []
    for i, el in enumerate(elements):
        tag = f"<{el['tag']}" + (f" type={el['type']}" if el["type"] else "") + ">"
        parts = [f"{i + 1}. {tag}"]
        if el["text"]:
            parts.append(f'"{el["text"]}"')
        for attr in ("id", "name", "testId"):
            if el[attr]:
                parts.append(f"{attr}={el[attr]}")
        lines.append(" ".join(parts))
    return "\n".join(lines)
