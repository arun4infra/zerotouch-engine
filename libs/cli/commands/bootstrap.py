"""Bootstrap command - thin orchestrator"""

import asyncio
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from cli.mcp_client import WorkflowMCPClient


async def bootstrap_command(pipeline_yaml_path: str = "platform/pipeline.yaml", skip_cache: bool = False):
    """Execute bootstrap pipeline"""
    console = Console()
    client = WorkflowMCPClient(
        server_command="./scripts/start-mcp-server.sh",
        server_args=["--allow-write"]
    )
    
    try:
        async with client.connect() as session:
            # Validate artifacts
            console.print("[cyan]Validating artifacts...[/cyan]")
            validation = await client.call_tool(session, "validate_artifacts", {"platform_yaml_path": "platform/platform.yaml"})
            
            if not validation.get("valid"):
                console.print(f"[red]Validation failed: {validation.get('error')}[/red]")
                return
            
            console.print("[green]✓ Artifacts validated[/green]")
            
            # List stages
            stages_data = await client.call_tool(session, "list_stages", {"pipeline_yaml_path": pipeline_yaml_path})
            stages = stages_data.get("stages", [])
            
            if not stages:
                console.print("[yellow]No stages to execute[/yellow]")
                return
            
            console.print(f"\n[bold]Executing {len(stages)} stages[/bold]\n")
            
            # Execute stages
            with Progress(SpinnerColumn(), TextColumn("[progress.description]"), console=console) as progress:
                for stage in stages:
                    stage_name = stage["name"]
                    task = progress.add_task(f"→ {stage_name}", total=None)
                    
                    stage_result = await client.call_tool(session, "execute_stage", {
                        "pipeline_yaml_path": pipeline_yaml_path,
                        "stage_name": stage_name,
                        "skip_cache": skip_cache
                    })
                    
                    if stage_result.get("success"):
                        cached = " (cached)" if stage_result.get("cached") else ""
                        console.print(f"[green]✓[/green] {stage_name}{cached}")
                    else:
                        console.print(f"[red]✗ {stage_name} failed[/red]")
                        console.print(f"[red]Error: {stage_result.get('error')}[/red]")
                        return
            
            console.print("\n[green]✓ Bootstrap completed successfully[/green]")
            
    except Exception as e:
        console.print(f"[red]Bootstrap failed: {e}[/red]")


def bootstrap(skip_cache: bool = False):
    """Sync wrapper for bootstrap command"""
    asyncio.run(bootstrap_command(skip_cache=skip_cache))
