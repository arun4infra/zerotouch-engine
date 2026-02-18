"""Choice input handler with arrow key selection"""

import questionary
from rich.console import Console


async def handle_choice_input(question: dict, console: Console) -> str:
    """Handle choice input with arrow key selection"""
    prompt_text = question["prompt"]
    choices = question.get("choices", [])
    default = question.get("default")
    
    if not choices:
        console.print("[red]Error: No choices available[/red]")
        return None
    
    # Convert choices to questionary format
    questionary_choices = []
    default_choice = None
    
    for choice in choices:
        if isinstance(choice, dict):
            choice_label = choice.get("label", choice.get("value"))
            choice_val = choice.get("value")
        else:
            choice_label = choice
            choice_val = choice
        
        questionary_choices.append(questionary.Choice(title=choice_label, value=choice_val))
        
        # Set default
        if default and choice_val == default:
            default_choice = questionary.Choice(title=choice_label, value=choice_val)
    
    answer = questionary.select(
        prompt_text,
        choices=questionary_choices,
        default=default_choice
    ).ask()
    
    if not answer:
        raise KeyboardInterrupt("Selection cancelled")
    
    return answer
