"""Bootstrap command - thin presentation layer"""

import asyncio
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ztp_cli.engine_bridge import PlatformConfigService, BootstrapOrchestrator


def bootstrap(skip_cache: bool = False):
    """Execute bootstrap pipeline"""
    asyncio.run(_bootstrap_async(skip_cache))


async def _bootstrap_async(skip_cache: bool = False):
    """Async bootstrap implementation"""
    console = Console()
    
    try:
        # Check platform config exists
        config_service = PlatformConfigService()
        
        if not config_service.exists():
            console.print("[red]Error: platform.yaml not found[/red]")
            console.print("[dim]Run 'ztc init' and 'ztc render' first[/dim]")
            return
        
        config = config_service.load()
        
        console.print("[cyan]Executing bootstrap pipeline...[/cyan]")
        console.print(f"[dim]Organization: {config.platform.organization}[/dim]")
        console.print(f"[dim]App: {config.platform.app_name}[/dim]")
        
        # Get stage count for display
        orchestrator = BootstrapOrchestrator()
        stages = orchestrator.list_stages()
        
        if not stages:
            console.print("[yellow]No stages to execute[/yellow]")
            return
        
        console.print(f"\n[bold]Executing {len(stages)} stages[/bold]\n")
        
        # Track progress with Rich
        stage_tasks = {}
        
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            
            def progress_callback(stage_name: str, status: str, message: str):
                """Handle progress updates from engine"""
                if status == 'start':
                    # Create progress task for this stage
                    stage_tasks[stage_name] = progress.add_task(f"→ {stage_name}", total=None)
                
                elif status == 'success':
                    # Remove progress task and show success
                    if stage_name in stage_tasks:
                        progress.remove_task(stage_tasks[stage_name])
                        del stage_tasks[stage_name]
                    console.print(f"[green]✓[/green] {stage_name}")
                
                elif status == 'cached':
                    # Remove progress task and show cached
                    if stage_name in stage_tasks:
                        progress.remove_task(stage_tasks[stage_name])
                        del stage_tasks[stage_name]
                    console.print(f"[green]✓[/green] {stage_name} [dim](cached)[/dim]")
                
                elif status == 'failed':
                    # Remove progress task and show error
                    if stage_name in stage_tasks:
                        progress.remove_task(stage_tasks[stage_name])
                        del stage_tasks[stage_name]
                    console.print(f"[red]✗ {stage_name} failed[/red]")
                    if message:
                        console.print(f"[red]{message}[/red]")
            
            # Execute pipeline (engine handles all logic)
            result = await orchestrator.execute(skip_cache=skip_cache, progress_callback=progress_callback)
        
        # Display final result
        if result.success:
            console.print("\n[green]✓ Bootstrap completed successfully[/green]")
            console.print(f"[dim]Stages executed: {result.stages_executed}, cached: {result.stages_cached}[/dim]")
        else:
            console.print(f"\n[red]✗ Bootstrap failed at stage: {result.failed_stage}[/red]")
            if result.error:
                console.print(f"[red]Error: {result.error}[/red]")
        
    except Exception as e:
        console.print(f"[red]Bootstrap error: {e}[/red]")
