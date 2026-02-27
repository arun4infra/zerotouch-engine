"""Core CLI commands"""

import typer
from ztp_cli.commands.init import init
from ztp_cli.commands.render import render
from ztp_cli.commands.sync import sync
from ztp_cli.commands.bootstrap import bootstrap

app = typer.Typer(help="ZeroTouch Platform CLI")


@app.command(name="init")
def init_cmd():
    """Initialize platform configuration"""
    init()


@app.command(name="render")
def render_cmd(
    debug: bool = typer.Option(False, "--debug", help="Preserve workspace on failure"),
    partial: list[str] = typer.Option(None, "--partial", help="Render specific adapters")
):
    """Generate platform artifacts"""
    render(debug=debug, partial=partial)


@app.command(name="sync")
def sync_cmd():
    """Sync platform manifests to control plane repository"""
    sync()


@app.command(name="bootstrap")
def bootstrap_cmd(
    skip_cache: bool = typer.Option(False, "--skip-cache", help="Ignore stage cache")
):
    """Execute bootstrap pipeline"""
    bootstrap(skip_cache=skip_cache)

