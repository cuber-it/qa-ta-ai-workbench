import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.command()
@click.pass_context
def models(ctx):
    """List available models for the configured provider."""
    from ..main import _get_provider
    provider = _get_provider(ctx)

    model_list = provider.get_models()
    default    = provider.get_default_model()

    table = Table(title=f"Models — {provider.provider_name}")
    table.add_column("Model", style="cyan")
    table.add_column("Default", style="green")

    for m in model_list:
        table.add_row(m, "✓" if m == default else "")

    console.print(table)
