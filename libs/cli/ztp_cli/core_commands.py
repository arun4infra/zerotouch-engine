"""Core CLI commands"""

import typer
from ztp_cli.commands.init import init
from ztp_cli.commands.render import render

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
