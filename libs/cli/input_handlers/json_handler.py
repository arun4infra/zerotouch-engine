"""JSON input handler with structured collection"""

import json
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table


async def handle_json_input(question: dict, console: Console) -> dict:
    """Handle JSON input with validation
    
    For array inputs with example in help_text, provides iterative collection.
    Otherwise falls back to raw JSON input.
    """
    prompt_text = question["prompt"]
    help_text = question.get("help_text", "")
    server_ips = question.get("server_ips", [])
    
    # Check if help_text contains a JSON array example
    if help_text.startswith('[{') and help_text.endswith('}]'):
        # Parse example to understand structure
        try:
            example = json.loads(help_text)
            if isinstance(example, list) and len(example) > 0 and isinstance(example[0], dict):
                # Structured array collection
                if server_ips:
                    # Use server IPs for iteration (Talos nodes case)
                    return await _collect_nodes_from_ips(server_ips, console)
                else:
                    # Generic array collection
                    return await _collect_json_array(prompt_text, example[0], console)
        except json.JSONDecodeError:
            pass
    
    # Fallback to raw JSON input
    return await _collect_raw_json(prompt_text, console)


async def _collect_nodes_from_ips(server_ips: list, console: Console) -> list:
    """Collect node configurations for given server IPs (Talos-specific)"""
    import questionary
    
    nodes = []
    
    for idx, ip in enumerate(server_ips, 1):
        console.print(f"\n[cyan]Server {idx} ({ip}):[/cyan]")
        
        # Get node name
        while True:
            try:
                name = Prompt.ask(f"  name")
            except (KeyboardInterrupt, EOFError):
                raise KeyboardInterrupt("User cancelled input")
            
            if name and name.strip():
                name = name.strip()
                break
            console.print("[red]  Server name is required[/red]")
        
        # Get role with arrow key selection (async version)
        try:
            role = await questionary.select(
                f"  role:",
                choices=["controlplane", "worker"]
            ).ask_async()
        except (KeyboardInterrupt, EOFError):
            raise KeyboardInterrupt("User cancelled input")
        
        if not role:
            raise KeyboardInterrupt("Selection cancelled")
        
        nodes.append({"name": name, "ip": ip, "role": role})
        
        nodes.append({"name": name, "ip": ip, "role": role})
    
    return nodes


async def _collect_json_array(prompt_text: str, example_item: dict, console: Console) -> list:
    """Collect array of objects iteratively"""
    console.print(f"\n[cyan]{prompt_text}[/cyan]")
    console.print(f"[dim]Example: {json.dumps(example_item)}[/dim]\n")
    
    items = []
    item_num = 1
    
    while True:
        console.print(f"[bold]Item {item_num}:[/bold]")
        item = {}
        
        # Collect each field from example
        for field_name, example_value in example_item.items():
            field_type = type(example_value).__name__
            
            while True:
                try:
                    value = Prompt.ask(f"  {field_name} ({field_type})")
                except (KeyboardInterrupt, EOFError):
                    raise KeyboardInterrupt("User cancelled input")
                
                if not value:
                    console.print(f"[red]  {field_name} is required[/red]")
                    continue
                
                # Type conversion based on example
                try:
                    if isinstance(example_value, int):
                        item[field_name] = int(value)
                    elif isinstance(example_value, bool):
                        item[field_name] = value.lower() in ['true', 'yes', 'y', '1']
                    else:
                        item[field_name] = value
                    break
                except ValueError:
                    console.print(f"[red]  Invalid {field_type}[/red]")
        
        items.append(item)
        
        # Show collected items
        _display_items_table(items, console)
        
        # Ask to add more
        try:
            add_more = Confirm.ask("\nAdd another item?", default=False)
        except (KeyboardInterrupt, EOFError):
            raise KeyboardInterrupt("User cancelled input")
        
        if not add_more:
            break
        
        item_num += 1
        console.print()
    
    return items


def _display_items_table(items: list, console: Console):
    """Display collected items in a table"""
    if not items:
        return
    
    table = Table(title="Collected Items", show_header=True)
    
    # Add columns from first item
    for field_name in items[0].keys():
        table.add_column(field_name, style="cyan")
    
    # Add rows
    for item in items:
        table.add_row(*[str(v) for v in item.values()])
    
    console.print()
    console.print(table)


async def _collect_raw_json(prompt_text: str, console: Console) -> dict:
    """Collect raw JSON input"""
    while True:
        try:
            value = Prompt.ask(prompt_text)
        except (KeyboardInterrupt, EOFError):
            raise KeyboardInterrupt("User cancelled input")
        
        if not value:
            console.print("[red]This field is required[/red]")
            continue
        
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON: {e}[/red]")

