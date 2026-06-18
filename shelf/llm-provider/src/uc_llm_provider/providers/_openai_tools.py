"""
OpenAI Tool-Use Transformation Helpers.

Wandelt zwischen dem generischen Block-Format (Anthropic-Style)
und dem OpenAI tool_calls / tool-role-Message Format.
"""
import json


def is_block(block, block_type: str) -> bool:
    """Prüft Block-Typ — funktioniert mit dicts und Pydantic-Models."""
    if isinstance(block, dict):
        return block.get("type") == block_type
    return getattr(block, "type", None) == block_type


def block_get(block, key: str, default=""):
    """Attribut aus Block lesen — funktioniert mit dicts und Pydantic-Models."""
    if isinstance(block, dict):
        return block.get(key, default)
    return getattr(block, key, default)


def translate_assistant_tool_msg(content: list) -> dict:
    """Assistant-Message mit tool_use Blöcken → OpenAI tool_calls Format."""
    text_parts = []
    tool_calls = []
    for block in content:
        if is_block(block, "tool_use"):
            tool_calls.append({
                "id": block_get(block, "id"),
                "type": "function",
                "function": {
                    "name": block_get(block, "name"),
                    "arguments": json.dumps(block_get(block, "input", {})),
                },
            })
        elif is_block(block, "text"):
            text_parts.append(block_get(block, "text"))
        elif isinstance(block, str):
            text_parts.append(block)
    msg: dict = {"role": "assistant", "content": "\n".join(text_parts) or ""}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


def translate_tool_result_msgs(content: list) -> list[dict]:
    """tool_result Blöcke → separate role:'tool' Messages für OpenAI."""
    return [
        {
            "role": "tool",
            "tool_call_id": block_get(block, "tool_use_id"),
            "content": block_get(block, "content"),
        }
        for block in content
        if is_block(block, "tool_result")
    ]


def parse_tool_calls_response(tool_calls: list) -> list[dict]:
    """OpenAI tool_calls Response → generische tool_use Blöcke."""
    return [
        {
            "type": "tool_use",
            "id": tc["id"],
            "name": tc["function"]["name"],
            "input": json.loads(tc["function"].get("arguments", "{}")),
        }
        for tc in tool_calls
    ]
