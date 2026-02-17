"""Init workflow for progressive input collection"""

import asyncio
from pathlib import Path
from typing import Dict, Any
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
import yaml

from ztc.registry.groups import SelectionGroup, build_selection_groups
from ztc.registry.versions import VersionRegistry


class InitWorkflow:
    """Progressive input collection workflow for platform configuration
    
    Implements wizard-style prompts with resume capability and dynamic
    adapter selection based on registry metadata.
    """
    
    def __init__(self, console: Console, adapter_registry: 'AdapterRegistry', version_registry: VersionRegistry = None):
        self.console = console
        self.registry = adapter_registry
        self.version_registry = version_registry or VersionRegistry()
        self.config = {}
        
        # Dynamically build selection groups from registry (no hardcoded lists)
        self.selection_groups = build_selection_groups(adapter_registry)
    
    def run(self, resume: bool = False) -> Dict[str, Any]:
        """Execute progressive input collection workflow
        
        Args:
            resume: If True, load existing platform.yaml and skip completed sections
            
        Returns:
            Complete platform configuration dictionary
        """
        
        # Start background version fetch
        self.version_registry.start_background_fetch()
        
        # Step 1: Load existing config if resuming
        if resume:
            platform_yaml = Path("platform/platform.yaml")
            if not platform_yaml.exists():
                platform_yaml = Path("platform.yaml")  # Fallback
            
            if platform_yaml.exists():
                self.config = self.load_existing_config()
                self.console.print(f"[green]✓[/green] Loaded existing {platform_yaml}")
        
        # Step 2-7: Process selection groups (data-driven, no hardcoded logic)
        for group in self.selection_groups:
            if group.name not in self.config:
                self.config[group.name] = self.handle_group_selection(group)
            
            # Collect adapter-specific inputs
            adapter = self.registry.get_adapter(self.config[group.name])
            self.collect_adapter_inputs(adapter)
            
            # Validate upstream context after collecting inputs
            self.validate_downstream_adapters(adapter)
        
        # Step 8: Generate platform.yaml
        self.write_platform_yaml()
        
        # Step 9: Display summary with version source notification
        self.display_summary()
        
        return self.config
    
    def load_existing_config(self) -> Dict[str, Any]:
        """Load existing platform.yaml configuration
        
        Returns:
            Configuration dictionary from platform.yaml
        """
        platform_yaml = Path("platform/platform.yaml")
        if not platform_yaml.exists():
            platform_yaml = Path("platform.yaml")  # Fallback to old location
        
        with open(platform_yaml, "r") as f:
            return yaml.safe_load(f)
    
    def handle_group_selection(self, group: SelectionGroup) -> str:
        """Handle exclusive selection with generic cleanup logic
        
        Args:
            group: SelectionGroup with options and default
            
        Returns:
            Selected adapter name
        """
        selection = Prompt.ask(
            group.prompt,
            choices=group.options,
            default=group.default
        )
        
        # Generic cleanup: remove conflicting options from config
        for option in group.options:
            if option != selection and option in self.config:
                self.console.print(f"[yellow]⚠ Removing conflicting config for '{option}'[/yellow]")
                del self.config[option]
        
        return selection
    
    def collect_adapter_inputs(self, adapter: 'PlatformAdapter'):
        """Collect inputs for specific adapter with Pydantic validation
        
        Args:
            adapter: PlatformAdapter instance to collect inputs for
        """
        from pydantic import ValidationError
        
        inputs = adapter.get_required_inputs()
        invalid_fields = []
        
        # Validate existing config using adapter's Pydantic model
        if adapter.name in self.config:
            try:
                adapter.config_model(**self.config[adapter.name])
                # Config is valid, skip all prompts for this adapter
                return
            except ValidationError as e:
                # Track invalid fields that need re-prompting
                invalid_fields = [err['loc'][0] for err in e.errors()]
                self.console.print(f"[yellow]⚠[/yellow] Found invalid values in {adapter.name} config, re-prompting...")
        
        for input_def in inputs:
            # Skip only if value exists AND is valid
            adapter_config = self.config.setdefault(adapter.name, {})
            if (input_def.name in adapter_config 
                and input_def.name not in invalid_fields):
                continue
            
            # Pre-fill with existing value if available (even if invalid)
            existing_value = adapter_config.get(input_def.name)
            if existing_value and input_def.name in invalid_fields:
                self.console.print(f"[red]Invalid value:[/red] {existing_value}")
            
            value = self.prompt_input(input_def, default_override=existing_value)
            self.config[adapter.name][input_def.name] = value
    
    def prompt_input(self, input_def: 'InputPrompt', default_override=None) -> Any:
        """Prompt for single input with validation
        
        Args:
            input_def: InputPrompt definition
            default_override: Override default value if provided
            
        Returns:
            User input value
        """
        default = default_override if default_override else input_def.default
        
        if input_def.type == "choice":
            return Prompt.ask(
                input_def.prompt,
                choices=input_def.choices,
                default=default
            )
        elif input_def.type == "boolean":
            return Confirm.ask(input_def.prompt, default=default)
        elif input_def.type == "password":
            return Prompt.ask(input_def.prompt, password=True)
        else:
            return Prompt.ask(input_def.prompt, default=default)
    
    def validate_downstream_adapters(self, changed_adapter: 'PlatformAdapter'):
        """Validate downstream adapters when upstream context changes (differential)
        
        Uses get_invalid_fields() to preserve valid config and only re-prompt invalid fields.
        
        Args:
            changed_adapter: Adapter that was just configured
        """
        for adapter_name in list(self.config.keys()):
            if adapter_name == changed_adapter.name:
                continue
            
            # Check if this adapter's config has invalid fields
            if adapter_name in self.registry.list_adapters():
                adapter = self.registry.get_adapter(adapter_name)
                current_config = self.config.get(adapter_name, {})
                
                # Get specific invalid fields (differential validation)
                invalid_fields = adapter.get_invalid_fields(current_config, self.config)
                
                if invalid_fields:
                    self.console.print(
                        f"[yellow]⚠ Fields {invalid_fields} in '{adapter_name}' are invalid "
                        f"due to changes in '{changed_adapter.name}'. Re-prompting...[/yellow]"
                    )
                    
                    # Only remove invalid fields, keep valid ones
                    for field in invalid_fields:
                        if field in current_config:
                            del current_config[field]
    
    def write_platform_yaml(self):
        """Generate and write platform.yaml configuration file"""
        platform_dir = Path("platform")
        platform_dir.mkdir(exist_ok=True)
        
        with open(platform_dir / "platform.yaml", "w") as f:
            yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
        
        self.console.print("[green]✓[/green] Generated platform/platform.yaml")
    
    def display_summary(self):
        """Display configuration summary table"""
        table = Table(title="Platform Configuration Summary")
        table.add_column("Adapter", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Configuration", style="yellow")
        
        for adapter_name, adapter_config in self.config.items():
            if isinstance(adapter_config, dict):
                version = adapter_config.get("version", "N/A")
                config_str = ", ".join(
                    f"{k}={v}" for k, v in adapter_config.items() 
                    if k != "version"
                )
                table.add_row(adapter_name, version, config_str)
        
        self.console.print(table)
        
        # Display version source notification
        version_source = self.version_registry.get_version_source()
        if "embedded" in version_source:
            self.console.print(f"\n[yellow]ℹ[/yellow] Using {version_source} versions")
            if self.version_registry.get_last_error():
                self.console.print(f"[dim]  Reason: {self.version_registry.get_last_error()}[/dim]")
        else:
            self.console.print(f"\n[green]✓[/green] Using {version_source} versions")
