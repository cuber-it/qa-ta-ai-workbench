import asyncio

import click
from rich.console import Console

from ...core.base import EndpointNotAvailable
from ...core.models import ChatCompletionRequest, Message

console = Console()


@click.command()
@click.argument("prompt")
@click.option("--system", "-s", default=None)
@click.option("--max-tokens", default=2048, type=int)
@click.pass_context
def stream(ctx, prompt, system, max_tokens):
    """Stream a response token by token."""
    from ..main import _get_provider
    provider = _get_provider(ctx)
    asyncio.run(_stream(provider, prompt, system, max_tokens))


async def _stream(provider, prompt, system, max_tokens):
    msgs = []
    if system:
        msgs.append(Message(role="system", content=system))
    msgs.append(Message(role="user", content=prompt))
    request = ChatCompletionRequest(
        model=provider.get_default_model(),
        messages=msgs,
        max_tokens=max_tokens,
    )
    try:
        async for chunk in provider.chat_stream(request):
            if chunk.type == "content_delta" and chunk.content:
                console.print(chunk.content, end="")
            elif chunk.type == "error":
                console.print(f"\n[red]Error: {chunk.error}[/red]")
                break
        console.print()
    except EndpointNotAvailable as e:
        console.print(f"[red]{e}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
