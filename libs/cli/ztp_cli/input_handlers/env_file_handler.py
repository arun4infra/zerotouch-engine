"""Environment file input handler"""

import re
from pathlib import Path
from rich.console import Console
from rich.prompt import Confirm


async def handle_env_file_input(question: dict, console: Console) -> str:
    """Handle input from .env.global file
    
    Loads value from .env.global and validates format.
    Used for sensitive data like private keys.
    """
    help_text = question.get("help_text", "")
    validation = question.get("validation")
    
    # Extract env var name from help_text (e.g., "GIT_APP_PRIVATE_KEY")
    env_var_match = re.search(r'\(([A-Z_]+)\)', help_text)
    if not env_var_match:
        console.print(f"[red]Error: Cannot determine env var name from help_text[/red]")
        return None
    
    env_var_name = env_var_match.group(1)
    prompt_text = question["prompt"]
    
    console.print(f"\n[yellow]{prompt_text} must be set in .env.global file[/yellow]")
    console.print(f"[dim]Add this line to .env.global:[/dim]")
    console.print(f'[dim]{env_var_name}="<your-value>"[/dim]')
    
    while True:
        try:
            ready = Confirm.ask(f"\nHave you added {env_var_name} to .env.global?")
        except (KeyboardInterrupt, EOFError):
            raise KeyboardInterrupt("User cancelled input")
        
        if not ready:
            console.print("[yellow]Please add the key to .env.global and try again[/yellow]")
            continue
        
        # Read .env.global
        env_file = Path(".env.global")
        if not env_file.exists():
            console.print("[red].env.global file not found[/red]")
            continue
        
        # Parse env file for the variable (handles multi-line values)
        with open(env_file) as f:
            content = f.read()
            # Match: VAR_NAME="value" (quotes required for multi-line)
            pattern = rf'{env_var_name}="(.*?)"'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                value = match.group(1)
                # Unescape \n to actual newlines
                value = value.replace('\\n', '\n')
            else:
                console.print(f"[red]{env_var_name} not found in .env.global[/red]")
                console.print(f"[dim]Make sure it's in format: {env_var_name}=\"...\"[/dim]")
                continue
        
        if not value:
            console.print(f"[red]{env_var_name} is empty in .env.global[/red]")
            continue
        
        # Validate against regex if provided
        if validation and not re.match(validation, value, re.DOTALL):
            console.print(f"[red]Invalid format for {env_var_name}[/red]")
            console.print(f"[dim]Expected: {help_text or validation}[/dim]")
            continue
        
        console.print(f"[green]✓[/green] Valid value loaded from .env.global")
        return value
