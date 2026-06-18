"""
uc-llm-provider Server — Entrypoint

Usage:
    uc-llm-server --port 12290 --provider anthropic --model claude-sonnet-4-20250514
    uc-llm-server --port 12290 --config server.yaml
"""
import click
import uvicorn

from .app import create_app
from .config import load_config


@click.command()
@click.option("--port",     required=True,  type=int,    help="Port to listen on")
@click.option("--provider", default=None,                help="Provider type (anthropic|openai|google|ollama|…)")
@click.option("--model",    default=None,                help="Default model")
@click.option("--api-key",  default=None, envvar="UC_LLM_API_KEY", help="API key")
@click.option("--api-base", default=None,                help="API base URL (for local providers)")
@click.option("--log-mode", default=None, type=click.Choice(["sqlite", "jsonl", "none"]), help="Log mode")
@click.option("--log-dir",  default=None,                help="Log directory")
@click.option("--config",   default=None, type=click.Path(exists=True), help="Config YAML file")
def main(port, provider, model, api_key, api_base, log_mode, log_dir, config):
    """Start the uc-llm-provider server."""
    cfg = load_config(
        port=port,
        provider=provider,
        model=model,
        api_key=api_key,
        api_base=api_base,
        log_mode=log_mode,
        log_dir=log_dir,
        config_file=config,
    )

    click.echo(f"Starting uc-llm-provider server on port {cfg.port}")
    click.echo(f"  Provider : {cfg.provider}")
    click.echo(f"  Model    : {cfg.model}")
    click.echo(f"  Log mode : {cfg.log_mode} → {cfg.log_dir}")

    app = create_app(cfg)
    uvicorn.run(app, host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    main()
