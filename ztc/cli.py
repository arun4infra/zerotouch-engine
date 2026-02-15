"""CLI entry point for ZTC"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from pathlib import Path
from typing import Optional, List
import asyncio
import sys

from ztc.exceptions import (
    ZTCError,
    MissingCapabilityError,
    LockFileValidationError,
    RuntimeDependencyError
)

app = typer.Typer(
    name="ztc",
    help="ZeroTouch Composition Engine - Bare-metal Kubernetes bootstrap",
    add_completion=False
)
console = Console()


def register_adapter_subcommands():
    """Discover and register adapter CLI extensions
    
    Registers commands under category names, not adapter names.
    Only one adapter per category can provide CLI commands.
    """
    from ztc.adapters.base import CLIExtension
    from ztc.registry.adapter_registry import AdapterRegistry
    from pathlib import Path
    import yaml
    
    # Check if platform.yaml exists
    platform_yaml = Path("platform/platform.yaml")
    if not platform_yaml.exists():
        platform_yaml = Path("platform.yaml")  # Fallback
    
    if not platform_yaml.exists():
        return  # No platform config, skip CLI registration
    
    try:
        # Load platform configuration
        with open(platform_yaml) as f:
            platform_config = yaml.safe_load(f)
        
        selected_adapters = platform_config.get("adapters", {})
        if not selected_adapters:
            return
        
        # Initialize registry
        registry = AdapterRegistry()
        
        # Track registered categories to prevent conflicts
        registered_categories = {}
        
        for adapter_name, adapter_config in selected_adapters.items():
            try:
                # Get adapter class
                adapter_instance = registry.get_adapter(adapter_name, adapter_config)
                
                # Check if adapter implements CLI extension
                if isinstance(adapter_instance, CLIExtension):
                    # Get category name (not adapter name)
                    category = adapter_instance.get_cli_category()
                    cli_app = adapter_instance.get_cli_app()
                    
                    if cli_app:
                        # Prevent multiple adapters from same category
                        if category in registered_categories:
                            console.print(
                                f"[yellow]Warning: Category '{category}' CLI already registered by "
                                f"'{registered_categories[category]}'. Skipping '{adapter_name}'.[/yellow]"
                            )
                            continue
                        
                        # Register under category name
                        app.add_typer(
                            cli_app,
                            name=category,
                            help=f"{category.title()} management tools"
                        )
                        
                        registered_categories[category] = adapter_name
            
            except Exception as e:
                # Skip adapters that fail to load
                console.print(f"[dim]Could not register CLI for '{adapter_name}': {e}[/dim]")
                continue
    
    except Exception as e:
        # Silently skip if platform.yaml is invalid
        pass


def handle_ztc_error(error: ZTCError, exit_code: int = 1):
    """Handle ZTC errors with Rich formatting
    
    Args:
        error: ZTC exception to handle
        exit_code: Exit code to use
    """
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
    error_text = Text()
    error_text.append("✗ Unexpected Error: ", style="bold red")
    error_text.append(str(error))
    
    console.print(error_text)
    console.print("\n[yellow]This is an unexpected error. Please report this issue.[/yellow]")
    console.print(f"[dim]Error type: {type(error).__name__}[/dim]")
    
    raise typer.Exit(exit_code)


def _run_automatic_vacuum():
    """Run vacuum silently on CLI startup."""
    from ztc.utils.vacuum import VacuumCommand
    
    # Silent vacuum - only shows output if stale dirs found
    vacuum_cmd = VacuumCommand(console)
    stale_dirs = vacuum_cmd.find_stale_directories()
    
    if stale_dirs:
        # Only execute if there are stale directories
        vacuum_cmd.execute()


@app.command()
def init(
    env: str = typer.Argument("dev", help="Environment (dev/staging/prod)")
):
    """Initialize platform configuration via interactive prompts"""
    from ztc.commands.init import InitCommand
    
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
    from ztc.engine import PlatformEngine
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    
    console.print("[bold blue]Rendering platform artifacts...[/bold blue]")
    
    if debug:
        console.print("[yellow]Debug mode enabled - workspace will be preserved on failure[/yellow]")
    
    if partial:
        console.print(f"[yellow]Partial render: {', '.join(partial)}[/yellow]")
    
    # Check if platform.yaml exists (try new location first)
    platform_yaml = Path("platform/platform.yaml")
    if not platform_yaml.exists():
        platform_yaml = Path("platform.yaml")  # Fallback to old location
    
    if not platform_yaml.exists():
        console.print("[red]Error: platform/platform.yaml not found[/red]")
        console.print("Run 'ztc init' to create platform configuration")
        raise typer.Exit(1)
    
    try:
        # Create engine
        engine = PlatformEngine(platform_yaml, debug=debug)
        
        # Run render with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Rendering...", total=None)
            
            def update_progress(description: str):
                progress.update(task, description=description)
            
            asyncio.run(engine.render(partial=partial, progress_callback=update_progress))
        
        console.print("[green]✓[/green] Render completed successfully")
        console.print(f"Artifacts written to: platform/generated/")
        console.print(f"Lock file: platform/lock.json")
        
    except ZTCError as e:
        handle_ztc_error(e)
    except Exception as e:
        if debug:
            console.print("[yellow]Workspace preserved at: .zerotouch-cache/workspace[/yellow]")
        handle_unexpected_error(e)


@app.command()
def validate():
    """Validate generated artifacts against lock file"""
    from ztc.commands.validate import ValidateCommand
    
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
    env: str = typer.Option("production", "--env", help="Target environment"),
    skip_cache: bool = typer.Option(False, "--skip-cache", help="Ignore stage cache")
):
    """Execute bootstrap pipeline"""
    from ztc.commands.bootstrap import BootstrapCommand
    
    console.print(f"[bold blue]Bootstrapping environment: {env}[/bold blue]")
    
    if skip_cache:
        console.print("[yellow]Stage cache will be ignored[/yellow]")
    
    try:
        bootstrap_cmd = BootstrapCommand(env, skip_cache)
        bootstrap_cmd.execute()
        
        console.print("[green]✓[/green] Bootstrap completed successfully")
        
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
    from ztc.workflows.eject import EjectWorkflow
    
    try:
        workflow = EjectWorkflow(console, Path(output_dir), env)
        workflow.run()
        
    except ZTCError as e:
        handle_ztc_error(e)
    except FileNotFoundError as e:
        console.print(f"[red]✗ File not found:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        handle_unexpected_error(e)


@app.command()
def vacuum():
    """Clean up stale temporary directories from crashed runs
    
    Removes ztc-secure-* directories older than 60 minutes from /tmp.
    Handles cases where SIGKILL prevented normal cleanup.
    """
    from ztc.utils.vacuum import VacuumCommand
    
    console.print("[bold blue]Cleaning up stale temporary directories...[/bold blue]")
    
    vacuum_cmd = VacuumCommand(console)
    vacuum_cmd.execute()


@app.command()
def version():
    """Display CLI version and embedded adapter versions"""
    from rich.table import Table
    from ztc.registry.adapter_registry import AdapterRegistry
    import importlib.metadata
    
    console.print("[bold blue]ZTC Version Information[/bold blue]\n")
    
    # Get CLI version from package metadata
    try:
        cli_version = importlib.metadata.version("ztc")
    except importlib.metadata.PackageNotFoundError:
        cli_version = "0.1.0-dev"
    
    console.print(f"CLI Version: [green]{cli_version}[/green]\n")
    
    # Display adapter versions
    try:
        registry = AdapterRegistry()
        registry.discover_adapters()
        
        table = Table(title="Embedded Adapter Versions")
        table.add_column("Adapter", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Phase", style="yellow")
        table.add_column("Provides", style="magenta")
        
        for adapter_name in sorted(registry.list_adapters()):
            adapter = registry.get_adapter(adapter_name)
            metadata = adapter.load_metadata()
            
            # Handle provides field - can be list of dicts or list of strings
            provides_list = metadata.get("provides", [])
            if provides_list:
                if isinstance(provides_list[0], dict):
                    # Extract capability names from dict format
                    provides = ", ".join(item.get("capability", "") for item in provides_list)
                else:
                    # Handle string format
                    provides = ", ".join(provides_list)
            else:
                provides = "none"
            
            table.add_row(
                metadata.get("display_name", adapter_name),
                metadata.get("version", "unknown"),
                metadata.get("phase", "unknown"),
                provides
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load adapter versions: {e}[/yellow]")


if __name__ == "__main__":
    # Run automatic vacuum on startup
    _run_automatic_vacuum()
    
    # Register adapter CLI subcommands
    register_adapter_subcommands()
    
    app()
