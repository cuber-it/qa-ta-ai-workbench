import asyncio

import click
from rich.console import Console
from rich.panel import Panel

from ...core.base import EndpointNotAvailable
from ...core.models import Message, TokenCountRequest

console = Console()


@click.command()
@click.argument("text")
@click.pass_context
def tokens(ctx, text):
    """Count tokens for a given text."""
    from ..main import _get_provider
    provider = _get_provider(ctx)
    asyncio.run(_count(provider, text))


async def _count(provider, text):
    request = TokenCountRequest(
        messages=[Message(role="user", content=text)],
        model=provider.get_default_model(),
    )
    try:
        result = await provider.count_tokens(request)
        console.print(Panel(
            f"[bold]{result.input_tokens}[/bold] tokens\n"
            f"Model: {result.model}",
            title="Token Count", border_style="blue"
        ))
    except EndpointNotAvailable:
        # Fallback: rough estimate
        est = len(text.split()) * 4 // 3
        console.print(Panel(
            f"~[bold]{est}[/bold] tokens (estimated)\n"
            f"[dim]Provider does not support token counting[/dim]",
            title="Token Count (estimate)", border_style="yellow"
        ))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
