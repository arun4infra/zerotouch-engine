"""Integer input handler"""

from rich.console import Console
from rich.prompt import Prompt


async def handle_integer_input(question: dict, console: Console) -> int:
    """Handle integer input with validation"""
    prompt_text = question["prompt"]
    
    while True:
        try:
            value = Prompt.ask(prompt_text)
        except (KeyboardInterrupt, EOFError):
            raise KeyboardInterrupt("User cancelled input")
        
        if not value:
            console.print("[red]This field is required[/red]")
            continue
        
        try:
            return int(value.strip())
        except ValueError:
            console.print("[red]Invalid number. Please enter an integer[/red]")
