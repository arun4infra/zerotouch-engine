"""Core CLI commands for ZTC lifecycle operations"""

import typer
from rich.console import Console
from pathlib import Path
from typing import Optional, List

# Import command classes from local commands module
from ztp_cli.commands.init import InitCommand
from ztp_cli.commands.render import RenderCommand
from ztp_cli.commands.validate import ValidateCommand
from ztp_cli.commands.bootstrap import BootstrapCommand
from ztp_cli.commands.eject import EjectCommand

# Import exceptions (need to copy these too)
from ztp_cli.exceptions import ZTCError

app = typer.Typer(
    name="core",
    help="Core lifecycle commands",
    add_completion=False
)
console = Console()


def handle_ztc_error(error: ZTCError, exit_code: int = 1):
    """Handle ZTC errors with Rich formatting
    
    Args:
        error: ZTC exception to handle
        exit_code: Exit code to use
    """
    from rich.panel import Panel
    from rich.text import Text
    
    # Create error message with formatting
    error_text = Text()
    error_text.append("✗ Error: ", style="bold red")
    error_text.append(error.message)
    
    # Create panel with error and help text
    if error.help_text:
        panel_content = f"{error.message}\n\n[bold cyan]Help:[/bold cyan]\n{error.help_text}"
    else:
        panel_content = error.message
    
    panel = Panel(
        panel_content,
        title="[bold red]Error[/bold red]",
        border_style="red",
        expand=False
    )
    
    console.print(panel)
    raise typer.Exit(exit_code)


def handle_unexpected_error(error: Exception, exit_code: int = 1):
    """Handle unexpected errors with Rich formatting
    
    Args:
        error: Exception to handle
        exit_code: Exit code to use
    """
    from rich.text import Text
    
    error_text = Text()
    error_text.append("✗ Unexpected Error: ", style="bold red")
    error_text.append(str(error))
    
    console.print(error_text)
    console.print("\n[yellow]This is an unexpected error. Please report this issue.[/yellow]")
    console.print(f"[dim]Error type: {type(error).__name__}[/dim]")
    
    raise typer.Exit(exit_code)


@app.command()
def init(
    env: str = typer.Argument("dev", help="Environment (dev/staging/prod)")
):
    """Initialize platform configuration via interactive prompts"""
    try:
        init_cmd = InitCommand(console, env=env)
        init_cmd.execute()
        
    except ZTCError as e:
        handle_ztc_error(e)
    except Exception as e:
        handle_unexpected_error(e)


@app.command()
def render(
    debug: bool = typer.Option(False, "--debug", help="Preserve workspace on failure"),
    partial: Optional[List[str]] = typer.Option(None, "--partial", help="Render specific adapters")
):
    """Generate platform artifacts from platform.yaml"""
    try:
        render_cmd = RenderCommand(console, debug=debug, partial=partial)
        render_cmd.execute()
    except ZTCError as e:
        handle_ztc_error(e)
    except Exception as e:
        if debug:
            console.print("[yellow]Workspace preserved at: .zerotouch-cache/workspace[/yellow]")
        handle_unexpected_error(e)


@app.command()
def validate():
    """Validate generated artifacts against lock file"""
    console.print("[bold blue]Validating artifacts...[/bold blue]")
    
    try:
        validate_cmd = ValidateCommand()
        validate_cmd.execute()
        
        console.print("[green]✓[/green] Validation passed")
        console.print("  - platform.yaml hash matches lock file")
        console.print("  - Generated artifacts hash matches lock file")
        
    except ZTCError as e:
        handle_ztc_error(e)
    except Exception as e:
        handle_unexpected_error(e)


@app.command()
def bootstrap(
    env: str = typer.Argument("production", help="Target environment (dev/staging/prod)"),
    skip_cache: bool = typer.Option(False, "--skip-cache", help="Ignore stage completion cache")
):
    """Execute bootstrap pipeline with stage caching"""
    try:
        bootstrap_cmd = BootstrapCommand(env=env, skip_cache=skip_cache)
        bootstrap_cmd.execute()
        
    except ZTCError as e:
        handle_ztc_error(e)
    except Exception as e:
        handle_unexpected_error(e)


@app.command()
def eject(
    env: str = typer.Option("production", "--env", help="Target environment"),
    output_dir: str = typer.Option("debug", "--output", help="Output directory for ejected artifacts")
):
    """Eject scripts and pipeline for manual debugging (break-glass mode)
    
    Extracts all embedded scripts, context files, and pipeline.yaml to a debug directory,
    allowing operators to inspect and manually execute bootstrap logic when CLI fails.
    
    Use cases:
    - Debugging failed bootstrap stages
    - Manual intervention during cluster setup
    - Understanding script execution flow
    - Customizing scripts for edge cases
    """
    try:
        eject_cmd = EjectCommand(console, output_dir, env)
        eject_cmd.execute()
    except ZTCError as e:
        handle_ztc_error(e)
    except FileNotFoundError as e:
        console.print(f"[red]✗ File not found:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        handle_unexpected_error(e)
