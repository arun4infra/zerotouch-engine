"""Validate command - thin orchestrator"""

import asyncio
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

from cli.mcp_client import WorkflowMCPClient


async def validate_command(platform_yaml_path: str = "platform.yaml"):
    """Validate generated artifacts"""
    console = Console()
    client = WorkflowMCPClient()
    
    try:
        async with client.connect() as session:
            # Validate artifacts
            console.print("[cyan]Validating artifacts against lock file...[/cyan]")
            result = await client.call_tool(session, "validate_artifacts", {"platform_yaml_path": platform_yaml_path})
            artifacts_validation = json.loads(result.content[0].text)
            
            if artifacts_validation.get("valid"):
                console.print("[green]✓ Artifacts match lock file[/green]")
            else:
                console.print(f"[red]✗ Artifact validation failed: {artifacts_validation.get('error')}[/red]")
            
            # Validate runtime dependencies
            console.print("\n[cyan]Checking runtime dependencies...[/cyan]")
            result = await client.call_tool(session, "validate_runtime_dependencies", {})
            deps_validation = json.loads(result.content[0].text)
            
            table = Table(title="Runtime Dependencies")
            table.add_column("Tool", style="cyan")
            table.add_column("Status")
            
            for tool, present in deps_validation.get("dependencies", {}).items():
                status = "[green]✓ Present[/green]" if present else "[red]✗ Missing[/red]"
                table.add_row(tool, status)
            
            console.print(table)
            
            if not deps_validation.get("valid"):
                missing = deps_validation.get("missing", [])
                console.print(f"\n[red]Missing dependencies: {', '.join(missing)}[/red]")
            
            # Validate cluster access
            console.print("\n[cyan]Checking cluster access...[/cyan]")
            result = await client.call_tool(session, "validate_cluster_access", {})
            cluster_validation = json.loads(result.content[0].text)
            
            if cluster_validation.get("accessible"):
                console.print("[green]✓ Cluster is accessible[/green]")
            else:
                console.print(f"[yellow]⚠ Cluster not accessible: {cluster_validation.get('error')}[/yellow]")
            
            # Summary
            all_valid = (
                artifacts_validation.get("valid") and
                deps_validation.get("valid") and
                cluster_validation.get("accessible")
            )
            
            if all_valid:
                console.print("\n[green]✓ All validations passed[/green]")
            else:
                console.print("\n[yellow]⚠ Some validations failed[/yellow]")
            
    except Exception as e:
        console.print(f"[red]Validation error: {e}[/red]")


def validate():
    """Sync wrapper for validate command"""
    asyncio.run(validate_command())
