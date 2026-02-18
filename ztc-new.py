#!/usr/bin/env python3
"""New ZTC CLI entry point"""
import sys
from pathlib import Path

# Add libs to path
libs_path = Path(__file__).parent / "libs"
sys.path.insert(0, str(libs_path))

import click
from cli.commands.init import init
from cli.commands.render import render
from cli.commands.bootstrap import bootstrap
from cli.commands.validate import validate


@click.group()
def cli():
    """ZeroTouch Composition Engine"""
    pass


@cli.command()
def init_cmd():
    """Initialize platform configuration"""
    init()


@cli.command()
@click.option("--partial", multiple=True, help="Render specific adapters only")
@click.option("--debug", is_flag=True, help="Preserve workspace on failure")
def render_cmd(partial, debug):
    """Render platform adapters"""
    render(partial=list(partial) if partial else None, debug=debug)


@cli.command()
@click.option("--skip-cache", is_flag=True, help="Ignore stage cache")
def bootstrap_cmd(skip_cache):
    """Execute bootstrap pipeline"""
    bootstrap(skip_cache=skip_cache)


@cli.command()
def validate_cmd():
    """Validate generated artifacts"""
    validate()


if __name__ == "__main__":
    cli()
