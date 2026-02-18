"""String input handler with validation"""

import re
from typing import Any
from rich.console import Console
from rich.prompt import Prompt


async def handle_string_input(question: dict, console: Console) -> Any:
    """Handle string input with validation
    
    Supports:
    - Single values
    - Comma-separated lists (for plural field names ending with 's')
    - Regex validation
    """
    prompt_text = question["prompt"]
    validation = question.get("validation")
    help_text = question.get("help_text")
    field_name = question.get("name", "")
    
    while True:
        try:
            value = Prompt.ask(prompt_text)
        except (KeyboardInterrupt, EOFError):
            raise KeyboardInterrupt("User cancelled input")
        
        if not value:
            console.print("[red]This field is required[/red]")
            continue
        
        value = value.strip()
        
        # Check if it's a list field (plural name ending with 's')
        if field_name.endswith("s"):
            # Parse as comma-separated list
            if "," in value:
                items = [v.strip() for v in value.split(",")]
            else:
                items = [value.strip()]
            
            # Validate each item if pattern provided
            if validation:
                invalid_items = [v for v in items if not re.match(validation, v)]
                if invalid_items:
                    console.print(f"[red]Invalid format for: {', '.join(invalid_items)}[/red]")
                    console.print(f"[red]Expected: {help_text or validation}[/red]")
                    continue
            
            return items
        else:
            # Single value validation
            if validation and not re.match(validation, value):
                console.print(f"[red]Invalid format. Expected: {help_text or validation}[/red]")
                continue
            
            return value
