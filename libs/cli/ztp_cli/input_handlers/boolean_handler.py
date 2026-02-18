"""Boolean input handler"""

from rich.console import Console
from rich.prompt import Confirm


async def handle_boolean_input(question: dict, console: Console) -> bool:
    """Handle boolean (yes/no) input"""
    prompt_text = question["prompt"]
    default = question.get("default", False)
    
    try:
        return Confirm.ask(prompt_text, default=default)
    except (KeyboardInterrupt, EOFError):
        raise KeyboardInterrupt("User cancelled input")
