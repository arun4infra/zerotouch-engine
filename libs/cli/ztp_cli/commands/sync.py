"""Sync command - syncs platform manifests to control plane repo"""

import asyncio
from rich.console import Console

from ztp_cli.engine_bridge import SyncOrchestrator


def sync():
    """Sync platform manifests to control plane repository"""
    asyncio.run(_sync_async())


async def _sync_async():
    """Async sync implementation"""
    console = Console()
    
    try:
        console.print("[cyan]Syncing platform manifests to control plane repository...[/cyan]")
        console.print()
        
        orchestrator = SyncOrchestrator()
        result = await orchestrator.execute()
        
        if not result.success:
            console.print(f"[red]✗ Sync failed: {result.error}[/red]")
            return
        
        if result.message == "No changes to sync":
            console.print("[green]✓ No changes to sync[/green]")
            console.print("[dim]All manifests are up to date[/dim]")
            return
        
        console.print("[green]✓ Sync completed successfully[/green]")
        
        if result.pr_url:
            console.print()
            console.print("[yellow]Action Required:[/yellow]")
            console.print(f"[green]PR URL: {result.pr_url}[/green]")
            console.print()
            console.print("[dim]Next steps:[/dim]")
            console.print("[dim]  1. Review and approve the PR[/dim]")
            console.print("[dim]  2. Merge the PR[/dim]")
            console.print("[dim]  3. Run: ztc bootstrap[/dim]")
        
    except Exception as e:
        console.print(f"[red]Sync error: {e}[/red]")
