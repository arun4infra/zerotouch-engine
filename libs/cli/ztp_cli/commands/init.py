"""Init command - thin presentation layer"""

import asyncio
import json
from pathlib import Path
from rich.console import Console
from rich.spinner import Spinner
from rich.live import Live

from ztp_cli.engine_bridge import InitWorkflowOrchestrator
from ztp_cli.input_handlers import get_input


class InitCommand:
    """Orchestrates the init workflow between CLI and MCP engine"""
    
    def __init__(self):
        self.console = Console()
        self.orchestrator = InitWorkflowOrchestrator()
        self.platform_yaml_path = Path("platform/platform.yaml")
        
    async def run(self):
        """Main orchestration flow"""
        try:
            # Pre-flight checks via engine
            if not self.orchestrator.check_prerequisites():
                self._display_prerequisite_error()
                return
            
            # Run workflow
            await self._run_workflow()
                
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
    
    def _display_prerequisite_error(self):
        """Display prerequisite check failure"""
        self.console.print(f"[yellow]Platform configuration already exists: {self.platform_yaml_path}[/yellow]")
        self.console.print("[yellow]Init process cannot run when platform.yaml exists.[/yellow]")
        self.console.print("[dim]To reconfigure, delete platform.yaml and run init again.[/dim]")
    
    async def _run_workflow(self):
        """Execute the init workflow"""
        self._show_header()
        
        # Start workflow via engine
        result = self.orchestrator.start()
        
        # Question loop
        try:
            while not result.completed:
                if result.error:
                    self.console.print(f"[red]Error: {result.error}[/red]")
                    break
                
                # Display question
                if result.question:
                    # Display context based on engine hints
                    self._display_context(result)
                    
                    # Check if engine wants auto-answer
                    if result.auto_answer:
                        answer = result.question.get("default")
                        self.console.print(f"[dim]{result.question.get('prompt')}: {answer} (auto-selected)[/dim]")
                    else:
                        # Display prompt and get user input
                        self.console.print(f"{result.question.get('prompt')}: ", end="")
                        answer = await get_input(result.question, self.console)
                        if answer is None:
                            continue
                    
                    # Submit to engine
                    result = await self.orchestrator.answer(result.state, answer)
                    
                    # Display validation results if present
                    if result.validation_results:
                        self._display_validation_results(result.validation_results)
                else:
                    break
            
            # Display completion
            if result.completed:
                self._handle_completion(result)
                
        except (KeyboardInterrupt, asyncio.CancelledError):
            raise  # Propagate to outer handler
    
    def _show_header(self):
        """Display init header"""
        self.console.print("[bold blue]ZeroTouch Composition Engine[/bold blue]")
        self.console.print("Interactive platform configuration wizard\n")
    

    

    
    def _display_context(self, result):
        """Display context based on engine hints"""
        # Display adapter header if engine signals
        if result.display_hint == "adapter_header":
            adapter_name = result.state.get("current_adapter_inputs", {}).get("adapter_name")
            if adapter_name:
                self.console.print(f"\n[bold]Configure {adapter_name}[/bold]")
        
        # Display validation error if engine signals
        elif result.display_hint == "validation_error":
            error = result.state.get("validation_error")
            if error:
                self._display_validation_error(error)
        
        # Show help text
        if result.question and result.question.get("help_text"):
            self.console.print(f"[dim]{result.question['help_text']}[/dim]")
    
    def _display_validation_error(self, error: dict):
        """Display validation failure details"""
        self.console.print(f"\n[red]✗ {error.get('script', 'Validation')} failed[/red]")
        if error.get("stderr"):
            self.console.print(f"[red]Error: {error['stderr']}[/red]")
        if error.get("stdout"):
            self.console.print(f"[yellow]Output: {error['stdout']}[/yellow]")
        self.console.print(f"[dim]Logs: .zerotouch-cache/init-logs/[/dim]\n")
    

    

    
    def _display_validation_results(self, scripts):
        """Display validation script results"""
        for script in scripts:
            # Handle both dict and object formats
            if isinstance(script, dict):
                success = script.get("success", False)
                description = script.get("description", "Unknown script")
            else:
                success = script.success
                description = script.description
            
            if success:
                self.console.print(f"[green]✓[/green] {description}")
            else:
                self.console.print(f"[red]✗[/red] {description}")
    
    def _handle_completion(self, result):
        """Handle successful workflow completion"""
        if result.platform_yaml_path:
            self.console.print(f"\n[green]✓ Configuration complete[/green]")
            self.console.print(f"[dim]Platform configuration saved to: {result.platform_yaml_path}[/dim]")
        else:
            self.console.print("[red]Error: No platform.yaml generated[/red]")
    
    def _handle_cancellation(self):
        """Handle user cancellation"""
        self.console.print("\n[yellow]Init cancelled by user[/yellow]")
    
    def _handle_error(self, error: Exception):
        """Handle unexpected errors"""
        import traceback
        self.console.print(f"[red]Error: {error}[/red]")
        self.console.print(f"[dim]{traceback.format_exc()}[/dim]")
    



async def init_command():
    """Entry point for init command"""
    command = InitCommand()
    await command.run()


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
