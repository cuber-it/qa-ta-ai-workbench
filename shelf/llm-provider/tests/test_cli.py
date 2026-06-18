"""test_cli.py — alle Subcommands mit CliRunner."""
import pytest
from click.testing import CliRunner

from uc_llm_provider.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "uc-llm" in result.output.lower() or "Usage" in result.output


def test_config_command(runner):
    result = runner.invoke(cli, ["--provider", "openai", "config"])
    assert result.exit_code == 0
    assert "openai" in result.output


def test_health_command(runner):
    result = runner.invoke(cli, ["--provider", "openai", "--api-key", "test", "health"])
    assert result.exit_code == 0
    assert "openai" in result.output


def test_models_command(runner):
    result = runner.invoke(cli, ["--provider", "openai", "models"])
    assert result.exit_code == 0


def test_tokens_command(runner):
    result = runner.invoke(cli, ["--provider", "openai", "tokens", "Hello world test"])
    assert result.exit_code == 0


def test_cli_unknown_provider(runner):
    result = runner.invoke(cli, ["--provider", "does_not_exist_xyz", "config"])
    # config does not instantiate the provider, should still work
    assert result.exit_code == 0
