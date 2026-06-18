import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.command()
@click.pass_context
def config(ctx):
    """Show active configuration."""
    obj = ctx.obj

    table = Table(title="Active Config")
    table.add_column("Key",   style="cyan")
    table.add_column("Value", style="white")

    table.add_row("provider",  obj.get("provider", "—"))
    table.add_row("model",     obj.get("model") or "(provider default)")
    table.add_row("api_base",  obj.get("api_base") or "(default)")
    table.add_row("api_key",   "***" if obj.get("api_key") else "(not set)")
    table.add_row("log_mode",  obj.get("log_mode", "none"))

    console.print(table)
