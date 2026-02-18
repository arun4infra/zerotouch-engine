"""Input handler registry and dispatcher"""

from typing import Any
from rich.console import Console

from .string_handler import handle_string_input
from .password_handler import handle_password_input
from .env_file_handler import handle_env_file_input
from .boolean_handler import handle_boolean_input
from .choice_handler import handle_choice_input
from .json_handler import handle_json_input
from .integer_handler import handle_integer_input


# Input handler registry
INPUT_HANDLERS = {
    "string": handle_string_input,
    "password": handle_password_input,
    "env_file": handle_env_file_input,
    "boolean": handle_boolean_input,
    "choice": handle_choice_input,
    "json": handle_json_input,
    "integer": handle_integer_input,
}


async def get_input(question: dict, console: Console) -> Any:
    """Get input based on question type
    
    Args:
        question: Question dict with type, prompt, validation, etc.
        console: Rich console for output
        
    Returns:
        User input value (type depends on question type)
    """
    question_type = question.get("type", "string")
    handler = INPUT_HANDLERS.get(question_type)
    
    if not handler:
        console.print(f"[red]Unknown input type: {question_type}[/red]")
        return None
    
    return await handler(question, console)
