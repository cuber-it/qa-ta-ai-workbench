# uc-llm-provider

A generic LLM provider abstraction, lifted into this workbench's `shelf/` as a
standalone building block.

One interface over Anthropic, OpenAI, Google, Ollama, and any OpenAI-compatible
endpoint. It talks to all of them over plain HTTP via `httpx`, so there are no
vendor SDKs to install or keep in sync. Core dependencies are just `httpx`,
`pydantic`, and `pyyaml`.

## Use

```python
from uc_llm_provider import ChatMessage, ChatRequest, get_provider

provider = get_provider("openai")          # reads the key from the environment
req = ChatRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="hi")])
resp = await provider.chat(req)
print(resp.content)
```

Tool use, streaming, and per-call cost logging (`uc_llm_provider.logging`) are
supported. The `server` and `cli` extras add an optional HTTP server and a
command-line client; neither is needed for library use.

## Install

Lives in the `shelf/` of the qa-ta-ai-workbench monorepo. Pull it straight from
Git, no PyPI:

```
pip install "uc-llm-provider @ git+https://github.com/cuber-it/qa-ta-ai-workbench.git#subdirectory=shelf/llm-provider"
```

Part of my QA/TA-with-AI experiments.
