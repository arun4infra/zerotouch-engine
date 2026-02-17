"""Render command implementation"""

import asyncio
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from ztc.engine import PlatformEngine
from ztc.exceptions import ZTCError


class RenderCommand:
    """Render command for generating platform artifacts from platform.yaml"""
    
    def __init__(self, console: Console, debug: bool = False, partial: Optional[List[str]] = None):
        """Initialize render command
        
        Args:
            console: Rich console for output
            debug: Preserve workspace on failure
            partial: List of specific adapters to render
        """
        self.console = console
        self.debug = debug
        self.partial = partial
    
    def execute(self):
        """Execute render pipeline"""
        self.console.print("[bold blue]Rendering platform artifacts...[/bold blue]")
        
        if self.debug:
            self.console.print("[yellow]Debug mode enabled - workspace will be preserved on failure[/yellow]")
        
        if self.partial:
            self.console.print(f"[yellow]Partial render: {', '.join(self.partial)}[/yellow]")
        
        # Check if platform.yaml exists (try new location first)
        platform_yaml = Path("platform/platform.yaml")
        if not platform_yaml.exists():
            platform_yaml = Path("platform.yaml")  # Fallback to old location
        
        if not platform_yaml.exists():
            self.console.print("[red]Error: platform/platform.yaml not found[/red]")
            self.console.print("Run 'ztc init' to create platform configuration")
            raise RuntimeError("platform.yaml not found")
        
        # Create engine
        engine = PlatformEngine(platform_yaml, debug=self.debug)
        
        # Run render with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("Rendering...", total=None)
            
            def update_progress(description: str):
                progress.update(task, description=description)
            
            asyncio.run(engine.render(partial=self.partial, progress_callback=update_progress))
        
        self.console.print("[green]✓[/green] Render completed successfully")
        self.console.print(f"Artifacts written to: platform/generated/")
        self.console.print(f"Lock file: platform/lock.json")
        self.console.print(f"[dim]Logs: .zerotouch-cache/render-logs/[/dim]")
