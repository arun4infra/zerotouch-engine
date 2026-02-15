"""Init command implementation"""

from pathlib import Path
from typing import Dict, List, Optional
import yaml
from rich.console import Console
from rich.prompt import Prompt, Confirm
import questionary

from ztc.registry.adapter_registry import AdapterRegistry


class InitCommand:
    """Initialize platform configuration via interactive prompts"""
    
    # Hardcoded selection group order
    SELECTION_ORDER = [
        "cloud_provider",
        "os",
        "network_tool",
        "gitops_platform",
        "infrastructure_provisioner",
        "DNS",
        "TLS",
        "gateway",
        "secrets_management"
    ]
    
    def __init__(self, console: Console, resume: bool = False):
        self.console = console
        self.resume = resume
        self.registry = AdapterRegistry()
        self.config = {}
        self.platform_yaml_path = Path("platform/platform.yaml")
    
    def execute(self):
        """Execute init workflow"""
        self.console.print("[bold blue]ZeroTouch Composition Engine[/bold blue]")
        self.console.print("Interactive platform configuration wizard\n")
        
        # Load existing config if resuming
        if self.resume:
            if self.platform_yaml_path.exists():
                self.config = self._load_existing_config()
                self.console.print("[green]✓[/green] Loaded existing platform.yaml\n")
            else:
                self.console.print("[yellow]No existing platform.yaml found, starting fresh[/yellow]\n")
        
        # Build selection groups from registry
        selection_groups = self._build_selection_groups()
        
        # Process each selection group in order
        for group in selection_groups:
            self._handle_group_selection(group)
        
        # Write platform.yaml
        self._write_platform_yaml()
        
        self.console.print("\n[green]✓[/green] Platform configuration complete")
        self.console.print(f"Configuration written to: {self.platform_yaml_path}")
    
    def _load_existing_config(self) -> Dict:
        """Load existing platform.yaml"""
        with open(self.platform_yaml_path) as f:
            data = yaml.safe_load(f)
        return data.get("adapters", {})
    
    def _build_selection_groups(self) -> List[Dict]:
        """Build selection groups from registry metadata"""
        groups_map = {}
        
        for adapter_name in self.registry.list_adapters():
            metadata = self.registry.get_metadata(adapter_name)
            selection_group = metadata.get("selection_group")
            
            # Skip adapters without selection_group or not in our order
            if not selection_group or selection_group not in self.SELECTION_ORDER:
                continue
            
            if selection_group not in groups_map:
                groups_map[selection_group] = {
                    "name": selection_group,
                    "prompt": metadata.get("group_prompt", f"Select {selection_group}"),
                    "help_text": metadata.get("group_help", ""),
                    "options": [],
                    "default": None
                }
            
            groups_map[selection_group]["options"].append(adapter_name)
            
            if metadata.get("is_default", False):
                groups_map[selection_group]["default"] = adapter_name
        
        # Return groups in specified order
        return [groups_map[group_name] for group_name in self.SELECTION_ORDER if group_name in groups_map]
    
    def _handle_group_selection(self, group: Dict):
        """Handle adapter selection for a group"""
        group_name = group["name"]
        
        # Skip if already configured and resuming
        if self.resume:
            # Check if any adapter from this group is already configured
            for adapter_name in group["options"]:
                if adapter_name in self.config:
                    self.console.print(f"[dim]Skipping {group_name} (already configured: {adapter_name})[/dim]")
                    return
        
        # Display group prompt
        self.console.print(f"\n[bold cyan]{group['prompt']}[/bold cyan]")
        if group["help_text"]:
            self.console.print(f"[dim]{group['help_text']}[/dim]\n")
        
        # Build choices with metadata
        choices = []
        for adapter_name in group["options"]:
            metadata = self.registry.get_metadata(adapter_name)
            display_name = metadata.get("display_name", adapter_name)
            version = metadata.get("version", "unknown")
            default_marker = " (default)" if adapter_name == group["default"] else ""
            choices.append({
                "name": f"{display_name} - v{version}{default_marker}",
                "value": adapter_name
            })
        
        # Get user selection with arrow keys
        default_choice = next((c for c in choices if c["value"] == group["default"]), choices[0])
        selected_adapter = questionary.select(
            "Select adapter:",
            choices=choices,
            default=default_choice
        ).ask()
        
        if not selected_adapter:
            raise KeyboardInterrupt("Selection cancelled")
        
        # Collect adapter-specific inputs
        adapter_config = self._collect_adapter_inputs(selected_adapter)
        
        # Store in config
        self.config[selected_adapter] = adapter_config
    
    def _collect_adapter_inputs(self, adapter_name: str) -> Dict:
        """Collect adapter-specific configuration inputs"""
        adapter = self.registry.get_adapter(adapter_name)
        inputs = adapter.get_required_inputs()
        
        if not inputs:
            return {}
        
        self.console.print(f"\n[bold]Configure {adapter_name}[/bold]")
        
        config = {}
        for input_prompt in inputs:
            # Skip BGP ASN if BGP not enabled
            if input_prompt.name == "bgp_asn" and not config.get("bgp_enabled", False):
                continue
            
            # Special handling for Talos nodes - iterate over Hetzner IPs
            if input_prompt.type == "json" and input_prompt.name == "nodes":
                nodes = []
                server_ips = self.config.get("hetzner", {}).get("server_ips", [])
                
                if not server_ips:
                    self.console.print("[red]No server IPs found from Hetzner config[/red]")
                    continue
                
                for ip in server_ips:
                    self.console.print(f"\n[cyan]Configure server: {ip}[/cyan]")
                    
                    name = Prompt.ask(f"Server name for {ip}")
                    role = questionary.select(
                        f"Role for {ip}:",
                        choices=["controlplane", "worker"]
                    ).ask()
                    
                    nodes.append({"name": name, "ip": ip, "role": role})
                
                config[input_prompt.name] = nodes
                continue
            
            if input_prompt.type == "boolean":
                value = Confirm.ask(input_prompt.prompt, default=input_prompt.default or False)
            elif input_prompt.type == "choice":
                value = Prompt.ask(
                    input_prompt.prompt,
                    choices=input_prompt.choices,
                    default=input_prompt.default
                )
            elif input_prompt.type == "password":
                while True:
                    value = Prompt.ask(input_prompt.prompt, password=True)
                    if value:
                        break
                    self.console.print("[red]This field is required[/red]")
            elif input_prompt.type == "json":
                import json
                while True:
                    value = Prompt.ask(input_prompt.prompt)
                    if value:
                        try:
                            value = json.loads(value)
                            break
                        except json.JSONDecodeError as e:
                            self.console.print(f"[red]Invalid JSON: {e}[/red]")
                    else:
                        self.console.print("[red]This field is required[/red]")
            else:
                while True:
                    # Show default in prompt if available
                    prompt_text = input_prompt.prompt
                    if input_prompt.default:
                        prompt_text = f"{input_prompt.prompt} [{input_prompt.default}]"
                    
                    value = Prompt.ask(prompt_text, default=str(input_prompt.default) if input_prompt.default else None)
                    if value:
                        # Validate against regex pattern if provided (before parsing)
                        if input_prompt.validation:
                            import re
                            # Check if it's a comma-separated list OR field name ends with 's'
                            if input_prompt.name.endswith("s"):
                                # Always treat as list for plural field names
                                if "," in value:
                                    items = [v.strip() for v in value.split(",")]
                                else:
                                    items = [value.strip()]
                                
                                # Validate each item
                                invalid_items = [v for v in items if not re.match(input_prompt.validation, v)]
                                if invalid_items:
                                    self.console.print(f"[red]Invalid format for: {', '.join(invalid_items)}[/red]")
                                    self.console.print(f"[red]Expected: {input_prompt.help_text or input_prompt.validation}[/red]")
                                    continue
                                value = items
                            else:
                                # Single value validation
                                if not re.match(input_prompt.validation, value):
                                    self.console.print(f"[red]Invalid format. Expected: {input_prompt.help_text or input_prompt.validation}[/red]")
                                    continue
                        else:
                            # No validation, just parse comma-separated lists for plural fields
                            if input_prompt.name.endswith("s"):
                                if "," in value:
                                    value = [v.strip() for v in value.split(",")]
                                else:
                                    value = [value.strip()]
                        break
                    self.console.print("[red]This field is required[/red]")
            
            config[input_prompt.name] = value
        
        return config
    
    def _write_platform_yaml(self):
        """Write platform.yaml configuration"""
        platform_data = {
            "version": "1.0",
            "adapters": self.config
        }
        
        # Ensure platform directory exists
        self.platform_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.platform_yaml_path, "w") as f:
            yaml.dump(platform_data, f, default_flow_style=False, sort_keys=False)
