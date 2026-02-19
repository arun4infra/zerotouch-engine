"""Password input handler with validation"""

import re
from rich.console import Console
from rich.prompt import Prompt


async def handle_password_input(question: dict, console: Console) -> str:
    """Handle password input with validation and non-interactive mode support"""
    from ztp_cli.input_handlers.env_handler import get_env_value, is_non_interactive
    
    prompt_text = question["prompt"]
    validation = question.get("validation")
    help_text = question.get("help_text")
    field_name = question.get("name", "")
    
    # Check for non-interactive mode
    if is_non_interactive():
        value = get_env_value(field_name)
        if value:
            console.print(f"[dim]{prompt_text}: *** (from env)[/dim]")
            return value.strip()
    
    while True:
        try:
            value = Prompt.ask(prompt_text, password=True)
        except (KeyboardInterrupt, EOFError):
            raise KeyboardInterrupt("User cancelled input")
        
        if not value:
            console.print("[red]This field is required[/red]")
            continue
        
        value = value.strip()
        
        # Validate if pattern provided
        if validation:
            # Special handling for RSA keys - normalize format
            if "RSA PRIVATE KEY" in validation:
                if "\\n" not in value and "\n" not in value:
                    value = value.replace("-----BEGIN RSA PRIVATE KEY-----", "-----BEGIN RSA PRIVATE KEY-----\n")
                    value = value.replace("-----END RSA PRIVATE KEY-----", "\n-----END RSA PRIVATE KEY-----")
            
            if not re.match(validation, value, re.DOTALL):
                console.print(f"[red]Invalid format. {help_text or validation}[/red]")
                continue
        
        return value
