"""Render command - thin presentation layer"""

import asyncio
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ztp_cli.engine_bridge import PlatformConfigService, RenderOrchestrator


def render(partial: list = None, debug: bool = False):
    """Render platform adapters"""
    asyncio.run(_render_async(partial, debug))


async def _render_async(partial: list = None, debug: bool = False):
    """Async render implementation"""
    console = Console()
    
    try:
        # Check platform config exists
        config_service = PlatformConfigService()
        
        if not config_service.exists():
            console.print("[red]Error: platform.yaml not found[/red]")
            console.print("[dim]Run 'ztc init' first to create platform configuration[/dim]")
            return
        
        config = config_service.load()
        
        console.print("[cyan]Rendering adapters...[/cyan]")
        console.print(f"[dim]Organization: {config.platform.organization}[/dim]")
        console.print(f"[dim]App: {config.platform.app_name}[/dim]")
        console.print(f"[dim]Adapters: {len(config.adapters)}[/dim]")
        
        # Execute render via orchestrator
        orchestrator = RenderOrchestrator()
        
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("", total=None)
            
            def update_progress(message: str):
                progress.update(task, description=message)
            
            result = await orchestrator.render(partial=partial, debug=debug, progress_callback=update_progress)
        
        if result.success:
            console.print(f"[green]✓ Render completed successfully[/green]")
            console.print(f"[dim]Artifacts: {result.artifacts_path}[/dim]")
            console.print(f"[dim]Lock file: {result.lock_file_path}[/dim]")
            console.print(f"[dim]Adapters rendered: {result.adapters_rendered}[/dim]")
        else:
            console.print(f"[red]✗ Render failed: {result.error}[/red]")
            if debug:
                console.print("[yellow]Debug mode: workspace preserved at .zerotouch-cache/workspace/[/yellow]")
        
    except Exception as e:
        console.print(f"[red]Render error: {e}[/red]")
