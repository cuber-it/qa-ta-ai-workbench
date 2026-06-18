# uc-playwright-driver

A plain [Playwright](https://playwright.dev) driver, lifted out of a larger MCP
tool package so it can stand on its own.

It is two things and nothing more:

- `BrowserClient` — owns a Playwright browser/context/page and its lifecycle.
- a flat set of tool functions in `uc_playwright_driver.tools` that each take the
  client as their first argument: navigation, interaction, content, locators,
  frames, tabs, storage, network, scripting.

No MCP, no server framework, no agent. Just the driver. Compose it however you
like.

## Use

```python
from uc_playwright_driver import BrowserClient
from uc_playwright_driver import tools as pw

c = BrowserClient({"headless": True})
await pw.navigate(c, url="https://example.com")
text = await pw.get_text(c, selector="h1")
await c.cleanup()
```

## Install

This lives in the `shelf/` of the qa-ta-ai-workbench monorepo. Pull it straight
from Git, no PyPI:

```
pip install "uc-playwright-driver @ git+https://github.com/cuber-it/qa-ta-ai-workbench.git#subdirectory=shelf/playwright-driver"
```

Part of my QA/TA-with-AI experiments.
