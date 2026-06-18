import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.command()
@click.pass_context
def health(ctx):
    """Check provider health and capabilities."""
    from ..main import _get_provider
    provider = _get_provider(ctx)

    h    = provider.health()
    caps = provider.get_capabilities()

    console.print(Panel(
        f"[bold]Provider[/bold]  : {h.provider}\n"
        f"[bold]Status[/bold]    : {'[green]ok[/green]' if h.status == 'ok' else h.status}\n"
        f"[bold]Model[/bold]     : {provider.get_default_model()}\n"
        f"[bold]Tier 1[/bold]    : {', '.join(caps.tiers.core) or '—'}\n"
        f"[bold]Tier 2[/bold]    : {', '.join(caps.tiers.extended) or '—'}\n"
        f"[bold]Features[/bold]  : {', '.join(k for k,v in caps.features.items() if v) or '—'}",
        title="uc-llm health", border_style="blue"
    ))
