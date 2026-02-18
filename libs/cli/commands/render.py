"""Render command - thin orchestrator"""

import asyncio
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from cli.mcp_client import WorkflowMCPClient


async def render_command(platform_yaml_path: str = "platform/platform.yaml", partial: list = None, debug: bool = False):
    """Render platform adapters"""
    console = Console()
    client = WorkflowMCPClient(
        server_command="./scripts/start-mcp-server.sh",
        server_args=["--allow-write"]
    )
    
    try:
        async with client.connect() as session:
            console.print("[cyan]Starting render...[/cyan]")
            
            with Progress(SpinnerColumn(), TextColumn("[progress.description]"), console=console) as progress:
                task = progress.add_task("Rendering adapters...", total=None)
                
                render_result = await client.call_tool(session, "render_adapters", {
                    "platform_yaml_path": platform_yaml_path,
                    "partial": partial if partial else [],
                    "debug": debug
                })
            
            if render_result.get("success"):
                console.print("[green]✓ Render completed successfully[/green]")
                console.print(f"[dim]Artifacts: platform/generated/[/dim]")
                console.print(f"[dim]Lock file: platform/lock.json[/dim]")
            else:
                error = render_result.get('error', 'Unknown error')
                console.print(f"[red]✗ Render failed: {error}[/red]")
                console.print(f"[dim]Full result: {render_result}[/dim]")
                if debug:
                    console.print("[yellow]Debug mode: workspace preserved at .zerotouch-cache/workspace/[/yellow]")
            
    except Exception as e:
        console.print(f"[red]Render error: {e}[/red]")


def render(partial: list = None, debug: bool = False):
    """Sync wrapper for render command"""
    asyncio.run(render_command(partial=partial, debug=debug))
