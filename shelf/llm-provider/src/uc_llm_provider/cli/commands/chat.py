import asyncio

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from ...core.models import ChatCompletionRequest, Message

console = Console()


@click.command()
@click.argument("prompt", required=False)
@click.option("--interactive", "-i", is_flag=True, help="Interactive REPL mode")
@click.option("--system", "-s", default=None, help="System prompt")
@click.option("--max-tokens", default=2048, type=int)
@click.pass_context
def chat(ctx, prompt, interactive, system, max_tokens):
    """Send a prompt and get a response."""
    from ..main import _get_provider
    provider = _get_provider(ctx)

    if interactive:
        _interactive_loop(provider, system, max_tokens)
    elif prompt:
        asyncio.run(_chat_once(provider, prompt, system, max_tokens))
    else:
        click.echo("Provide a prompt or use --interactive", err=True)


async def _chat_once(provider, prompt, system, max_tokens):
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
        resp = await provider.chat(request)
        console.print(Markdown(resp.content))
        console.print(
            f"\n[dim]{resp.model} · {resp.usage.get('input_tokens',0)}↑ "
            f"{resp.usage.get('output_tokens',0)}↓ tokens[/dim]"
        )
    except Exception as e:
        console.print(Panel(str(e), title="Error", border_style="red"))


def _interactive_loop(provider, system, max_tokens):
    history: list[Message] = []
    console.print(Panel(
        f"Provider: {provider.provider_name}  Model: {provider.get_default_model()}\n"
        "Type 'exit' or Ctrl+C to quit, 'clear' to reset history.",
        title="uc-llm interactive", border_style="blue"
    ))

    while True:
        try:
            prompt = click.prompt("You", prompt_suffix=" > ")
        except (click.Abort, EOFError):
            break
        if prompt.strip().lower() in ("exit", "quit"):
            break
        if prompt.strip().lower() == "clear":
            history.clear()
            console.print("[dim]History cleared.[/dim]")
            continue

        history.append(Message(role="user", content=prompt))
        msgs = []
        if system:
            msgs = [Message(role="system", content=system)]
        request = ChatCompletionRequest(
            model=provider.get_default_model(),
            messages=msgs + history,
            max_tokens=max_tokens,
        )

        try:
            resp = asyncio.run(provider.chat(request))
            console.print(Markdown(resp.content))
            console.print(f"[dim]{resp.model} · {resp.usage.get('input_tokens',0)}↑ {resp.usage.get('output_tokens',0)}↓[/dim]")
            history.append(Message(role="assistant", content=resp.content))
        except Exception as e:
            console.print(Panel(str(e), title="Error", border_style="red"))
