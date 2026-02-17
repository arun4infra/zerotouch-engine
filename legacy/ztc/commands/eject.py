"""Eject command implementation"""

from pathlib import Path
from rich.console import Console

from ztc.workflows.eject import EjectWorkflow


class EjectCommand:
    """Eject command for extracting bootstrap artifacts for manual debugging"""
    
    def __init__(self, console: Console, output_dir: str, env: str):
        """Initialize eject command
        
        Args:
            console: Rich console for output
            output_dir: Directory to extract artifacts to
            env: Environment name (e.g., "production")
        """
        self.console = console
        self.output_dir = Path(output_dir)
        self.env = env
    
    def execute(self):
        """Execute eject workflow"""
        workflow = EjectWorkflow(self.console, self.output_dir, self.env)
        workflow.run()
