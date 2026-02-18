"""Init command - workflow-based orchestrator"""

import asyncio
import json
from pathlib import Path
from rich.console import Console

from cli.mcp_client import WorkflowMCPClient
from cli.input_handlers import get_input


async def init_command():
    """Initialize platform configuration via workflow"""
    console = Console()
    
    # Check if platform.yaml already exists
    platform_yaml_path = Path("platform/platform.yaml")
    if platform_yaml_path.exists():
        console.print(f"[yellow]Platform configuration already exists: {platform_yaml_path}[/yellow]")
        console.print("[yellow]Init process cannot run when platform.yaml exists.[/yellow]")
        console.print("[dim]To reconfigure, delete platform.yaml and run init again.[/dim]")
        return
    
    client = WorkflowMCPClient(
        server_command="./scripts/start-mcp-server.sh",
        server_args=["--allow-write"]
    )
    
    # State file for workflow
    state_file = Path(".zerotouch-cache/init-state.json")
    state_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        async with client.connect() as session:
            console.print("[bold blue]ZeroTouch Composition Engine[/bold blue]")
            console.print("Interactive platform configuration wizard\n")
            
            # Show spinner while loading adapters
            from rich.spinner import Spinner
            with console.status("[red]Loading adapters...[/red]", spinner="dots"):
                result = await client.call_tool(session, "init_start", {})
            
            if "error" in result:
                console.print(f"[red]Error: {result['error']}[/red]")
                return
            
            console.print("[bold cyan]Platform Metadata[/bold cyan]")
            console.print("[dim]This information helps generate consistent naming across all resources[/dim]\n")
            
            # Process questions
            while not result.get("completed"):
                question = result.get("question")
                workflow_state = result.get("workflow_state")
                
                if not question:
                    console.print("[red]Error: No question received[/red]")
                    break
                
                # Save state
                state_file.write_text(workflow_state)
                
                # Display question
                prompt_text = question["prompt"]
                question_id = question["id"]
                
                # Show section headers for selection groups and adapter configs
                if question_id.endswith("_selection"):
                    group_name = question_id.replace("_selection", "").replace("_", " ").title()
                    console.print(f"\n[bold cyan]Select {group_name}[/bold cyan]")
                elif question_id.startswith(tuple(f"{g}_input_" for g in ["cloud_provider", "secrets_management", "os", "network_tool", "gitops_platform", "infrastructure_provisioner"])):
                    # Extract adapter name from state
                    state = json.loads(workflow_state)
                    if "current_adapter_inputs" in state:
                        adapter_name = state["current_adapter_inputs"]["adapter_name"]
                        # Only show header for first input
                        if state["current_adapter_inputs"]["current_index"] == 0:
                            console.print(f"\n[bold]Configure {adapter_name}[/bold]")
                
                if question.get("help_text"):
                    console.print(f"[dim]{question['help_text']}[/dim]")
                
                # Show validation error details if present
                if question_id.endswith("_validation_failed"):
                    state = json.loads(workflow_state)
                    if "validation_error" in state:
                        error = state["validation_error"]
                        console.print(f"\n[red]✗ {error.get('script', 'Validation')} failed[/red]")
                        if error.get("stderr"):
                            console.print(f"[red]Error: {error['stderr']}[/red]")
                        if error.get("stdout"):
                            console.print(f"[yellow]Output: {error['stdout']}[/yellow]")
                        console.print(f"[dim]Logs: .zerotouch-cache/init-logs/[/dim]\n")
                
                # Get answer based on type
                answer_value = None
                question_type = question["type"]
                default = question.get("default")
                
                # Handle auto-derived values (skip user input)
                if question_type == "auto_derived":
                    value = question.get("value")
                    console.print(f"[dim]{prompt_text}: {value} (auto-derived)[/dim]")
                    answer_value = value
                # Auto-select if default exists (matching legacy)
                elif default is not None and question_type in ["string", "choice"]:
                    answer_value = default
                    console.print(f"[dim]{prompt_text}: {default} (auto-selected)[/dim]")
                else:
                    # Use input handler for this type
                    answer_value = await get_input(question, console)
                    if answer_value is None:
                        continue  # Retry or cancelled
                
                # Submit answer
                from rich.spinner import Spinner
                from rich.live import Live
                
                # Show spinner while waiting for response
                with Live(Spinner("dots", text="[cyan]Processing...[/cyan]"), console=console, transient=True):
                    result = await client.call_tool(session, "init_answer", {
                        "workflow_state": workflow_state,
                        "answer_value": str(answer_value)
                    })
                
                # Show validation results if present
                if "validation_scripts" in result:
                    for script in result["validation_scripts"]:
                        if script.get("success"):
                            console.print(f"[green]✓[/green] {script['description']}")
                        else:
                            console.print(f"[red]✗[/red] {script['description']}")
                
                if "error" in result:
                    console.print(f"[red]Error: {result['error']}[/red]")
                    break
            
            # Workflow complete
            if result.get("completed"):
                platform_yaml = result.get("platform_yaml")
                if platform_yaml:
                    platform_yaml_path.parent.mkdir(parents=True, exist_ok=True)
                    platform_yaml_path.write_text(platform_yaml)
                    console.print(f"\n[green]✓ Configuration complete[/green]")
                    console.print(f"[dim]Platform configuration saved to: {platform_yaml_path}[/dim]")
                    
                    # Cleanup state file
                    if state_file.exists():
                        state_file.unlink()
                else:
                    console.print("[red]Error: No platform.yaml generated[/red]")
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Init cancelled by user[/yellow]")
        if state_file.exists():
            state_file.unlink()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def init():
    """Sync wrapper for init command"""
    asyncio.run(init_command())

