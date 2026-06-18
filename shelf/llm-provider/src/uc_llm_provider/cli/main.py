"""
uc-llm — CLI Hauptgruppe

Usage:
    uc-llm chat "Erkläre mir Playwright"
    uc-llm chat --interactive
    uc-llm stream "Erkläre mir Playwright"
    uc-llm models
    uc-llm tokens "Wie viele Tokens hat dieser Text?"
    uc-llm health
    uc-llm config
"""
import os

import click

from ..factory import get_provider
from .commands.chat import chat
from .commands.config import config
from .commands.health import health
from .commands.models import models
from .commands.stream import stream
from .commands.tokens import tokens


@click.group()
@click.option("--provider",   default=None, envvar="UC_LLM_PROVIDER", help="Provider type")
@click.option("--model",      default=None, envvar="UC_LLM_MODEL",    help="Model")
@click.option("--api-key",    default=None, envvar="UC_LLM_API_KEY",  help="API key")
@click.option("--api-base",   default=None, envvar="UC_LLM_API_BASE", help="API base URL")
@click.option("--server-url", default=None, envvar="UC_LLM_SERVER",   help="Server URL")
@click.option("--log-mode",   default="none", type=click.Choice(["sqlite", "jsonl", "none"]), help="Log mode")
@click.pass_context
def cli(ctx, provider, model, api_key, api_base, server_url, log_mode):
    """uc-llm — Generic LLM CLI"""
    ctx.ensure_object(dict)
    ctx.obj["provider"]   = provider or "openai"
    ctx.obj["model"]      = model
    ctx.obj["api_key"]    = api_key or ""
    ctx.obj["api_base"]   = api_base or ""
    ctx.obj["server_url"] = server_url
    ctx.obj["log_mode"]   = log_mode


def _get_provider(ctx):
    cfg = {
        "name":          ctx.obj["provider"],
        "provider_type": ctx.obj["provider"],
        "api_key":       ctx.obj["api_key"],
    }
    if ctx.obj["model"]:
        cfg["default_model"] = ctx.obj["model"]
    if ctx.obj["api_base"]:
        cfg["api_base"] = ctx.obj["api_base"]
    os.environ["UC_LLM_COST_LOG"] = "false" if ctx.obj["log_mode"] == "none" else "true"
    return get_provider(cfg)


cli.add_command(chat)
cli.add_command(stream)
cli.add_command(models)
cli.add_command(tokens)
cli.add_command(health)
cli.add_command(config)
