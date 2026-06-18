"""
MCP-Client — fest eingebauter Client, dynamisch konfigurierbare Server.

Keine Server per Default, keine Server-Pakete als Abhaengigkeit. Server
werden zur Laufzeit per Config angelegt (HTTP bevorzugt, SSE moeglich),
ein Primaerziel ist waehlbar. Optionale Header pro Server (z.B. Bearer-Token
fuer OAuth-geschuetzte Proxies).

Verbindungen sind transient: pro Operation wird verbunden, gelistet/
aufgerufen, geschlossen -- robust, ohne Session-Lifecycle im Web-Server.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / ".git").exists():
            return p
    return here.parents[2]


_CFG_PATH = _repo_root() / "data" / "mcp_servers.json"


# ── Config ──────────────────────────────────────────────────────────────────
def load_config() -> dict:
    if _CFG_PATH.exists():
        try:
            return json.loads(_CFG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"servers": {}, "primary": None}


def _save(cfg: dict) -> None:
    _CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def list_servers() -> dict:
    """Server-Liste ohne Header-Geheimnisse (nur has_auth-Flag)."""
    cfg = load_config()
    servers = {}
    for name, s in cfg.get("servers", {}).items():
        view = {k: v for k, v in s.items() if k != "headers"}
        view["has_auth"] = bool(s.get("headers"))
        servers[name] = view
    return {"servers": servers, "primary": cfg.get("primary")}


def add_server(name: str, url: str, transport: str = "http",
               headers: dict | None = None) -> dict:
    if transport not in ("http", "sse"):
        raise ValueError("transport muss 'http' oder 'sse' sein")
    if not name or not url:
        raise ValueError("name und url erforderlich")
    cfg = load_config()
    cfg["servers"][name] = {
        "transport": transport, "url": url,
        "headers": headers or {}, "enabled": True,
    }
    if cfg.get("primary") is None:
        cfg["primary"] = name
    _save(cfg)
    return list_servers()


def remove_server(name: str) -> dict:
    cfg = load_config()
    cfg["servers"].pop(name, None)
    if cfg.get("primary") == name:
        cfg["primary"] = next(iter(cfg["servers"]), None)
    _save(cfg)
    return list_servers()


def set_primary(name: str) -> dict:
    cfg = load_config()
    if name not in cfg.get("servers", {}):
        raise KeyError(name)
    cfg["primary"] = name
    _save(cfg)
    return list_servers()


def _server_cfg(name: str | None) -> tuple[str, dict]:
    cfg = load_config()
    name = name or cfg.get("primary")
    if not name or name not in cfg.get("servers", {}):
        raise KeyError(name or "(kein Primaerziel gesetzt)")
    return name, cfg["servers"][name]


# ── Verbindung (transient) ──────────────────────────────────────────────────
@asynccontextmanager
async def _session(name: str | None):
    _, s = _server_cfg(name)
    url = s["url"]
    headers = s.get("headers") or None
    if s.get("transport") == "sse":
        async with sse_client(url, headers=headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    else:  # http (streamable-http)
        async with streamablehttp_client(url, headers=headers) as (read, write, _get_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


# ── Operationen ─────────────────────────────────────────────────────────────
async def list_tools(name: str | None = None) -> list[dict]:
    async with _session(name) as session:
        res = await session.list_tools()
        return [
            {"name": t.name, "description": t.description or "",
             "input_schema": t.inputSchema or {}}
            for t in res.tools
        ]


async def call_tool(name: str | None, tool: str, arguments: dict | None = None) -> dict:
    async with _session(name) as session:
        res = await session.call_tool(tool, arguments or {})
        parts = []
        for c in res.content:
            txt = getattr(c, "text", None)
            parts.append(txt if txt is not None else str(c))
        return {
            "is_error": bool(getattr(res, "isError", False)),
            "content":  "\n".join(parts),
            "structured": getattr(res, "structuredContent", None),
        }


async def test(name: str | None = None) -> dict:
    async with _session(name) as session:
        res = await session.list_tools()
        return {"ok": True, "tool_count": len(res.tools),
                "tools": [t.name for t in res.tools]}
