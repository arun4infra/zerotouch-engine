"""Init command - thin orchestrator"""

import asyncio
import json
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table

from cli.mcp_client import WorkflowMCPClient


async def init_command():
    """Initialize platform configuration"""
    console = Console()
    client = WorkflowMCPClient()
    
    try:
        async with client.connect() as session:
            # List adapters
            result = await client.call_tool(session, "list_adapters", {})
            adapters_data = json.loads(result.content[0].text)
            adapters = adapters_data.get("adapters", [])
            
            if not adapters:
                console.print("[red]No adapters available[/red]")
                return
            
            # Display adapter table
            table = Table(title="Available Adapters")
            table.add_column("Index", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Version")
            table.add_column("Description")
            
            for i, adapter in enumerate(adapters):
                table.add_row(
                    str(i),
                    adapter["name"],
                    adapter.get("version", "unknown"),
                    adapter.get("description", "")
                )
            
            console.print(table)
            
            # Select adapter
            choice = Prompt.ask("Select adapter index")
            selected = adapters[int(choice)]
            adapter_name = selected["name"]
            
            # Get adapter inputs
            result = await client.call_tool(session, "get_adapter_inputs", {"adapter_name": adapter_name})
            inputs_data = json.loads(result.content[0].text)
            inputs = inputs_data.get("inputs", [])
            
            # Collect configuration
            config = {}
            if inputs:
                console.print(f"\n[bold]Configure {adapter_name}[/bold]")
                for inp in inputs:
                    name = inp["name"]
                    prompt_text = inp.get("description", name)
                    required = inp.get("required", False)
                    
                    if required:
                        config[name] = Prompt.ask(f"{prompt_text} (required)")
                    else:
                        value = Prompt.ask(f"{prompt_text} (optional)", default="")
                        if value:
                            config[name] = value
            
            # Get project name
            project_name = Prompt.ask("Project name")
            
            # Generate platform YAML
            result = await client.call_tool(session, "generate_platform_yaml", {
                "project_name": project_name,
                "adapter_name": adapter_name,
                "config": config
            })
            yaml_data = json.loads(result.content[0].text)
            yaml_content = yaml_data.get("yaml_content", "")
            
            # Confirm and save
            if Confirm.ask(f"Generate platform.yaml for {project_name}?"):
                Path("platform.yaml").write_text(yaml_content)
                console.print("[green]✓ Created platform.yaml[/green]")
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def init():
    """Sync wrapper for init command"""
    asyncio.run(init_command())
