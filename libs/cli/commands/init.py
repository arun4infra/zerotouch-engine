"""Init command orchestrator - coordinates workflow between CLI and MCP engine"""

import asyncio
import json
from pathlib import Path
from rich.console import Console
from rich.spinner import Spinner
from rich.live import Live

from cli.mcp_client import WorkflowMCPClient
from cli.input_handlers import get_input


class InitOrchestrator:
    """Orchestrates the init workflow between CLI and MCP engine"""
    
    def __init__(self):
        self.console = Console()
        self.state_file = Path(".zerotouch-cache/init-state.json")
        self.platform_yaml_path = Path("platform/platform.yaml")
        
    async def run(self):
        """Main orchestration flow"""
        try:
            # Pre-flight checks
            if not self._check_prerequisites():
                return
            
            # Initialize MCP client
            client = WorkflowMCPClient(
                server_command="./scripts/start-mcp-server.sh",
                server_args=["--allow-write"]
            )
            
            # Run workflow
            async with client.connect() as session:
                await self._run_workflow(session, client)
                
        except (KeyboardInterrupt, asyncio.CancelledError, BaseExceptionGroup) as e:
            # Handle both direct interrupts and exception groups
            if isinstance(e, BaseExceptionGroup):
                self._handle_cancellation()
                raise KeyboardInterrupt()
            else:
                self._handle_cancellation()
                raise
        except Exception as e:
            self._handle_error(e)
    
    def _check_prerequisites(self) -> bool:
        """Check if init can run"""
        if self.platform_yaml_path.exists():
            self.console.print(f"[yellow]Platform configuration already exists: {self.platform_yaml_path}[/yellow]")
            self.console.print("[yellow]Init process cannot run when platform.yaml exists.[/yellow]")
            self.console.print("[dim]To reconfigure, delete platform.yaml and run init again.[/dim]")
            return False
        
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        return True
    
    async def _run_workflow(self, session, client):
        """Execute the init workflow"""
        self._show_header()
        
        # Start workflow - get first result
        result = await self._start_workflow(session, client)
        
        # Question loop
        try:
            while True:
                # Process current result
                if result.get("completed"):
                    self._handle_completion(result)
                    break
                
                if "error" in result:
                    self.console.print(f"[red]Error: {result['error']}[/red]")
                    break
                
                # Display question and get answer
                question = result.get("question")
                if question:
                    workflow_state = result.get("workflow_state")
                    state = json.loads(workflow_state) if workflow_state else {}
                    
                    # Load platform config from filesystem and inject into state
                    platform_config = self._load_platform_config()
                    state["platform_adapters_config"] = platform_config
                    workflow_state = json.dumps(state)
                    
                    # Auto-derived fields are now hidden - engine auto-processes them
                    
                    # Display context
                    self._display_question_context(question, state)
                    
                    # Get answer
                    answer_value = await self._get_answer(question)
                    if answer_value is None:
                        continue
                    
                    # Submit and get next result
                    result = await self._submit_answer(session, client, workflow_state, answer_value)
                    
                    # If validation completed (key exists), save adapter config
                    if "validation_scripts" in result:
                        self._save_adapter_to_yaml(result, state)
                else:
                    break
                
        except (KeyboardInterrupt, asyncio.CancelledError):
            raise  # Propagate to outer handler
    
    def _show_header(self):
        """Display init header"""
        self.console.print("[bold blue]ZeroTouch Composition Engine[/bold blue]")
        self.console.print("Interactive platform configuration wizard\n")
    
    async def _start_workflow(self, session, client) -> dict:
        """Start the init workflow and get first question"""
        with Live(Spinner("dots", text="[red]Loading adapters...[/red]"), console=self.console, transient=True):
            result = await client.call_tool(session, "init_start", {})
        
        if "error" in result:
            raise RuntimeError(f"Failed to start workflow: {result['error']}")
        
        return result
    
    async def _process_question_and_answer(self, session, client, result: dict) -> dict:
        """Process a single question and get answer"""
        question = result.get("question")
        workflow_state = result.get("workflow_state")
        
        if not question:
            return result
        
        # Parse state for context
        state = json.loads(workflow_state) if workflow_state else {}
        
        # Display question context
        self._display_question_context(question, state)
        # Display question context
        self._display_question_context(question, state)
        
        # Get answer from user
        answer_value = await self._get_answer(question)
        
        if answer_value is None:
            return result  # Retry or skip
        
        # Submit answer to engine
        return await self._submit_answer(session, client, workflow_state, answer_value)
    
    def _display_question_context(self, question: dict, state: dict):
        """Display section headers and help text"""
        question_id = question.get("id", "")
        
        # Show section headers for adapter configuration
        if "_input_" in question_id and "current_adapter_inputs" in state:
            adapter_name = state["current_adapter_inputs"]["adapter_name"]
            current_index = state["current_adapter_inputs"]["current_index"]
            
            # Show header only for first input
            if current_index == 0:
                self.console.print(f"\n[bold]Configure {adapter_name}[/bold]")
        
        # Show help text
        if question.get("help_text"):
            self.console.print(f"[dim]{question['help_text']}[/dim]")
        
        # Show validation error details if present
        if question_id.endswith("_validation_failed") and "validation_error" in state:
            self._display_validation_error(state["validation_error"])
    
    def _display_validation_error(self, error: dict):
        """Display validation failure details"""
        self.console.print(f"\n[red]✗ {error.get('script', 'Validation')} failed[/red]")
        if error.get("stderr"):
            self.console.print(f"[red]Error: {error['stderr']}[/red]")
        if error.get("stdout"):
            self.console.print(f"[yellow]Output: {error['stdout']}[/yellow]")
        self.console.print(f"[dim]Logs: .zerotouch-cache/init-logs/[/dim]\n")
    
    async def _get_answer(self, question: dict) -> any:
        """Get answer from user based on question type"""
        question_type = question.get("type")
        prompt_text = question.get("prompt")
        default = question.get("default")
        
        # Handle auto-selected defaults
        if default is not None and question_type in ["string", "choice"]:
            self.console.print(f"[dim]{prompt_text}: {default} (auto-selected)[/dim]")
            return default
        
        # Get user input
        return await get_input(question, self.console)
    
    async def _submit_answer(self, session, client, workflow_state: str, answer_value: any) -> dict:
        """Submit answer to engine and get next question"""
        import json
        
        # Show spinner while processing
        with Live(Spinner("dots", text="[cyan]Processing...[/cyan]"), console=self.console, transient=True):
            result = await client.call_tool(session, "init_answer", {
                "workflow_state": workflow_state,
                "answer_value": json.dumps(answer_value) if not isinstance(answer_value, str) else answer_value
            })
        
        # Display validation results if present
        if "validation_scripts" in result:
            self._display_validation_results(result["validation_scripts"])
        
        return result
    
    def _display_validation_results(self, scripts: list):
        """Display validation script results"""
        for script in scripts:
            if script.get("success"):
                self.console.print(f"[green]✓[/green] {script['description']}")
            else:
                self.console.print(f"[red]✗[/red] {script['description']}")
    
    def _handle_completion(self, result: dict):
        """Handle successful workflow completion"""
        platform_yaml = result.get("platform_yaml")
        
        if platform_yaml:
            self.platform_yaml_path.parent.mkdir(parents=True, exist_ok=True)
            self.platform_yaml_path.write_text(platform_yaml)
            self.console.print(f"\n[green]✓ Configuration complete[/green]")
            self.console.print(f"[dim]Platform configuration saved to: {self.platform_yaml_path}[/dim]")
            
            # Cleanup state file
            if self.state_file.exists():
                self.state_file.unlink()
        else:
            self.console.print("[red]Error: No platform.yaml generated[/red]")
    
    def _handle_cancellation(self):
        """Handle user cancellation"""
        self.console.print("\n[yellow]Init cancelled by user[/yellow]")
        if self.state_file.exists():
            self.state_file.unlink()
    
    def _handle_error(self, error: Exception):
        """Handle unexpected errors"""
        import traceback
        self.console.print(f"[red]Error: {error}[/red]")
        self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
    
    def _save_adapter_to_yaml(self, result: dict, state: dict):
        """Incrementally save adapter config to platform.yaml"""
        import yaml
        
        # Extract adapter info from state
        new_state = json.loads(result.get("workflow_state", "{}"))
        
        # Find which adapter just completed
        for key, value in new_state.get("answers", {}).items():
            if key.endswith("_config") and key not in state.get("answers", {}):
                # This is the newly added config
                adapter_name = new_state["answers"].get(key.replace("_config", "_selection"))
                config = value
                
                # Load existing platform.yaml or create new
                if self.platform_yaml_path.exists():
                    with open(self.platform_yaml_path) as f:
                        platform_data = yaml.safe_load(f) or {}
                else:
                    platform_data = {
                        "version": "1.0",
                        "platform": {
                            "organization": new_state["answers"].get("org_name"),
                            "app_name": new_state["answers"].get("app_name")
                        },
                        "adapters": {}
                    }
                
                # Add adapter config (already cleaned by engine)
                platform_data["adapters"][adapter_name] = config
                
                # Write back
                self.platform_yaml_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.platform_yaml_path, 'w') as f:
                    yaml.dump(platform_data, f, sort_keys=False, default_flow_style=False)
                
                self.console.print(f"[dim]✓ Saved {adapter_name} config to platform.yaml[/dim]")
                break
    
    def _load_platform_config(self) -> dict:
        """Load current platform.yaml for cross-adapter access"""
        import yaml
        
        if self.platform_yaml_path.exists():
            with open(self.platform_yaml_path) as f:
                data = yaml.safe_load(f) or {}
                return data.get("adapters", {})
        return {}


async def init_command():
    """Entry point for init command"""
    orchestrator = InitOrchestrator()
    await orchestrator.run()


def init():
    """Sync wrapper for init command"""
    import signal
    import sys
    
    # Set up signal handler for clean exit
    def signal_handler(signum, frame):
        print("\n[yellow]Init cancelled by user[/yellow]")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        asyncio.run(init_command())
    except KeyboardInterrupt:
        print("\n[yellow]Init cancelled by user[/yellow]")
        sys.exit(0)
