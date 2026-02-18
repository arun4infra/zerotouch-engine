"""UI/Display layer for workflow CLI"""
from typing import Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt


class QuestionRenderer:
    """Render workflow questions using rich"""
    
    def __init__(self, console: Optional[Console] = None):
        """Initialize renderer
        
        Args:
            console: Rich console instance
        """
        self.console = console or Console()
    
    def render_question(self, question: Dict[str, Any]) -> None:
        """Render question in panel
        
        Args:
            question: Question dictionary from MCP server
        """
        if not question:
            return
        
        # Build question content
        content_parts = [f"[bold]{question['prompt']}[/bold]"]
        content_parts.append(f"Type: {question['type']}")
        content_parts.append(f"ID: {question['id']}")
        
        if question.get('help_text'):
            content_parts.append(f"\n[dim]{question['help_text']}[/dim]")
        
        if question.get('default') is not None:
            default_display = "[REDACTED]" if question.get('sensitive') else question['default']
            content_parts.append(f"\nDefault: {default_display}")
        
        if question.get('sensitive'):
            content_parts.append("\n[yellow]⚠ Sensitive field - input will be hidden[/yellow]")
        
        content = "\n".join(content_parts)
        
        self.console.print(Panel(
            content,
            title="Question",
            border_style="cyan"
        ))
    
    def render_completion(self) -> None:
        """Render workflow completion message"""
        self.console.print("[green]✓ Workflow completed![/green]")
    
    def render_session_started(self, session_id: str) -> None:
        """Render session started message
        
        Args:
            session_id: Session identifier
        """
        self.console.print(f"\n[green]✓[/green] Session started: {session_id}")
        self.console.print(f"[dim]Use 'ztc-workflow answer {session_id} <value>' to respond[/dim]")
    
    def render_error(self, message: str) -> None:
        """Render error message
        
        Args:
            message: Error message
        """
        self.console.print(f"[red]✗ Error:[/red] {message}")
    
    def render_session_not_found(self, session_id: str) -> None:
        """Render session not found error
        
        Args:
            session_id: Session identifier
        """
        self.console.print(f"[red]✗ Session not found:[/red] {session_id}")
    
    def render_restore_hint(self, session_id: str) -> None:
        """Render hint for answering after restore
        
        Args:
            session_id: Session identifier
        """
        self.console.print(f"\n[dim]Use 'ztc-workflow answer {session_id} <value>' to respond[/dim]")
