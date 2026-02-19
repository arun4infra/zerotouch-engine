"""Bootstrap command - thin presentation layer"""

from pathlib import Path
from rich.console import Console

from ztp_cli.engine_bridge import PlatformConfigService


def bootstrap(skip_cache: bool = False):
    """Execute bootstrap pipeline"""
    console = Console()
    
    try:
        # Load platform config via engine
        config_service = PlatformConfigService()
        
        if not config_service.exists():
            console.print("[red]Error: platform.yaml not found[/red]")
            console.print("[dim]Run 'ztc init' and 'ztc render' first[/dim]")
            return
        
        config = config_service.load()
        
        console.print("[cyan]Executing bootstrap pipeline...[/cyan]")
        console.print(f"[dim]Organization: {config.platform.organization}[/dim]")
        console.print(f"[dim]App: {config.platform.app_name}[/dim]")
        
        # TODO: Implement bootstrap logic in workflow_engine
        console.print("[yellow]⚠ Bootstrap implementation pending migration to workflow_engine[/yellow]")
        
    except Exception as e:
        console.print(f"[red]Bootstrap error: {e}[/red]")
