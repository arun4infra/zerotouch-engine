"""Init command implementation"""

from pathlib import Path
from typing import Dict, List, Optional
from ruamel.yaml import YAML
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
import questionary

from ztc.registry.adapter_registry import AdapterRegistry
from ztc.engine.script_executor import ScriptExecutor
from ztc.adapters.base import InputPrompt


class InitCommand:
    """Initialize platform configuration via interactive prompts"""
    
    # Hardcoded selection group order
    SELECTION_ORDER = [
        "cloud_provider",
        "git_provider",
        "secrets_management",
        "os",
        "network_tool",
        "gitops_platform",
        "infrastructure_provisioner",
        "DNS",
        "TLS",
        "gateway"
    ]
    
    def __init__(self, console: Console, env: str = "dev"):
        self.console = console
        self.env = env
        self.registry = AdapterRegistry()
        self.config = {}
        self.platform_config = {}  # Store platform metadata
        self.secrets_cache = {}  # Store secrets separately from config
        self.env_vars = {}
        self.platform_yaml_path = Path("platform/platform.yaml")
        self.yaml = YAML()
        self.yaml.default_flow_style = False
        self.yaml.preserve_quotes = True
        self.yaml.width = 999999  # Disable line wrapping completely
        self.yaml.indent(mapping=2, sequence=2, offset=0)  # offset=0 for proper list item alignment
        
        # Load environment variables from .env file
        self._load_env_file()
    
    def _load_env_file(self):
        """Load environment variables from .env.{env} file"""
        env_file = Path(f".env.{self.env}")
        if not env_file.exists():
            self.console.print(f"[yellow]Warning: {env_file} not found, using defaults[/yellow]")
            return
        
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    self.env_vars[key.strip()] = value.strip()
        
        self.console.print(f"[green]✓[/green] Loaded environment from {env_file}")
    
    def execute(self):
        """Execute init workflow"""
        self.console.print("[bold blue]ZeroTouch Composition Engine[/bold blue]")
        self.console.print("Interactive platform configuration wizard\n")
        
        # Check if platform.yaml already exists
        if self.platform_yaml_path.exists():
            self.console.print(f"[yellow]Platform configuration already exists: {self.platform_yaml_path}[/yellow]")
            self.console.print("[yellow]Init process cannot run when platform.yaml exists.[/yellow]")
            self.console.print("[dim]To reconfigure, delete platform.yaml and run init again.[/dim]")
            return
        
        # Collect platform metadata first
        self._collect_platform_metadata()
        
        # Build selection groups from registry
        selection_groups = self._build_selection_groups()
        
        # Process each selection group in order
        for group in selection_groups:
            self._handle_group_selection(group)
        
        # Persist secrets to ~/.ztc/secrets
        self._write_secrets_file()
        
        self.console.print("\n[green]✓ Init phase complete[/green]")
        self.console.print(f"Configuration written to: {self.platform_yaml_path}")
        if self.secrets_cache:
            self.console.print(f"Secrets written to: ~/.ztc/secrets")
    
    def _load_existing_config(self) -> Dict:
        """Load existing platform.yaml"""
        with open(self.platform_yaml_path) as f:
            data = self.yaml.load(f)
        return data.get("adapters", {})
    
    def _collect_platform_metadata(self):
        """Collect platform-level metadata (app name, organization)"""
        self.console.print("[bold cyan]Platform Metadata[/bold cyan]")
        self.console.print("[dim]This information helps generate consistent naming across all resources[/dim]\n")
        
        # Organization name first
        while True:
            org_name = Prompt.ask("Organization name (GitHub org or username)").strip()
            if not org_name:
                self.console.print("[red]Organization name is required[/red]")
                continue
            
            self.platform_config['organization'] = org_name
            break
        
        # App name (must be org name followed by app name)
        while True:
            app_name = Prompt.ask("Application name (lowercase, hyphens only)").strip().lower()
            if not app_name:
                self.console.print("[red]Application name is required[/red]")
                continue
            
            # Validate format: lowercase alphanumeric with hyphens
            import re
            if not re.match(r'^[a-z0-9-]+$', app_name):
                self.console.print("[red]Invalid format. Use lowercase letters, numbers, and hyphens only[/red]")
                continue
            
            # Validate that app_name starts with org_name
            if not app_name.startswith(org_name.lower()):
                self.console.print(f"[red]Application name must start with organization name: {org_name.lower()}-[/red]")
                self.console.print(f"[dim]Example: {org_name.lower()}-myapp[/dim]")
                continue
            
            self.platform_config['app_name'] = app_name
            break
        
        self.console.print(f"\n[green]✓[/green] Platform metadata collected")
        self.console.print(f"[dim]  Org: {self.platform_config['organization']}[/dim]")
        self.console.print(f"[dim]  App: {self.platform_config['app_name']}[/dim]\n")
    
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
        
        # Auto-select if only one option
        if len(group["options"]) == 1:
            selected_adapter = group["options"][0]
            metadata = self.registry.get_metadata(selected_adapter)
            display_name = metadata.get("display_name", selected_adapter)
            self.console.print(f"\n[bold cyan]{group['prompt']}[/bold cyan]")
            self.console.print(f"[dim]Auto-selected: {display_name} (only option)[/dim]")
        else:
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
        
        # Write incrementally for resume support
        self._write_platform_yaml()
        
        # Execute init scripts for this adapter
        self._execute_init_scripts(selected_adapter)
    
    def _collect_adapter_inputs(self, adapter_name: str) -> Dict:
        """Collect adapter-specific configuration inputs"""
        adapter = self.registry.get_adapter(adapter_name)
        
        # Provide platform metadata and cross-adapter config to adapter
        adapter.set_platform_metadata(self.platform_config)
        adapter.set_all_adapters_config(self.config)
        
        inputs = adapter.get_required_inputs()
        
        if not inputs:
            return {}
        
        self.console.print(f"\n[bold]Configure {adapter_name}[/bold]")
        
        # Get adapter config model to detect SecretStr fields
        secret_fields = self._get_secret_fields(adapter.config_model)
        
        config = {}
        for input_prompt in inputs:
            # Check if adapter wants to skip this field
            if adapter.should_skip_field(input_prompt.name, config):
                continue
            
            # Check if adapter can derive this field's value
            derived_value = adapter.derive_field_value(input_prompt.name, config)
            if derived_value is not None:
                config[input_prompt.name] = derived_value
                self.console.print(f"[dim]{input_prompt.prompt}: {derived_value} (auto-derived)[/dim]")
                continue
            
            # Check if adapter provides custom collection logic
            custom_value = adapter.collect_field_value(input_prompt, config)
            if custom_value is not None:
                # Store in appropriate location (secrets_cache or config)
                if input_prompt.name in secret_fields:
                    if adapter_name not in self.secrets_cache:
                        self.secrets_cache[adapter_name] = {}
                    self.secrets_cache[adapter_name][input_prompt.name] = custom_value
                else:
                    config[input_prompt.name] = custom_value
                continue
            
            # Get suggestion from adapter
            suggestion = adapter.get_field_suggestion(input_prompt.name)
            if suggestion:
                self.console.print(f"[dim]Suggested: {suggestion}[/dim]")
            
            # Check if value exists in .env.{env} file (priority over defaults)
            env_key = f"{adapter_name.upper()}_{input_prompt.name.upper()}"
            if env_key in self.env_vars:
                value = self.env_vars[env_key]
                config[input_prompt.name] = value
                self.console.print(f"[dim]{input_prompt.prompt}: {value} (from .env.{self.env})[/dim]")
                continue
            
            # Auto-select if default exists (skip prompt)
            if input_prompt.default is not None:
                config[input_prompt.name] = input_prompt.default
                self.console.print(f"[dim]{input_prompt.prompt}: {input_prompt.default} (auto-selected)[/dim]")
                continue
            
            # Standard input collection
            value = self._collect_standard_input(input_prompt)
            
            # Store in appropriate location (secrets_cache or config)
            if input_prompt.name in secret_fields:
                if adapter_name not in self.secrets_cache:
                    self.secrets_cache[adapter_name] = {}
                self.secrets_cache[adapter_name][input_prompt.name] = value
            else:
                config[input_prompt.name] = value
        
        return config
    
    def _collect_standard_input(self, input_prompt: InputPrompt) -> any:
        """Standard input collection logic for different input types
        
        Args:
            input_prompt: The InputPrompt definition for this field
        
        Returns:
            The collected value
        """
        if input_prompt.type == "boolean":
            return Confirm.ask(input_prompt.prompt, default=input_prompt.default or False)
        elif input_prompt.type == "choice":
            return Prompt.ask(
                input_prompt.prompt,
                choices=input_prompt.choices,
                default=input_prompt.default
            )
        elif input_prompt.type == "password":
            while True:
                value = Prompt.ask(input_prompt.prompt, password=True)
                if value:
                    value = value.strip()
                    # Validate password fields if pattern provided
                    if input_prompt.validation:
                        import re
                        # For RSA keys, accept both single-line and multi-line format
                        if "RSA PRIVATE KEY" in input_prompt.validation:
                            # Normalize: if single line, add newlines after headers
                            if "\\n" not in value and "\n" not in value:
                                value = value.replace("-----BEGIN RSA PRIVATE KEY-----", "-----BEGIN RSA PRIVATE KEY-----\n")
                                value = value.replace("-----END RSA PRIVATE KEY-----", "\n-----END RSA PRIVATE KEY-----")
                        
                        if not re.match(input_prompt.validation, value, re.DOTALL):
                            self.console.print(f"[red]Invalid format. {input_prompt.help_text}[/red]")
                            continue
                    break
                self.console.print("[red]This field is required[/red]")
            return value
        elif input_prompt.type == "json":
            import json
            while True:
                value = Prompt.ask(input_prompt.prompt)
                if value:
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError as e:
                        self.console.print(f"[red]Invalid JSON: {e}[/red]")
                else:
                    self.console.print("[red]This field is required[/red]")
        else:
            # String type
            while True:
                prompt_text = input_prompt.prompt
                if input_prompt.default:
                    prompt_text = f"{input_prompt.prompt} [{input_prompt.default}]"
                
                value = Prompt.ask(prompt_text, default=str(input_prompt.default) if input_prompt.default else None)
                if value:
                    value = value.strip()
                    # Validate against regex pattern if provided
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
                            return items
                        else:
                            # Single value validation
                            if not re.match(input_prompt.validation, value):
                                self.console.print(f"[red]Invalid format. Expected: {input_prompt.help_text or input_prompt.validation}[/red]")
                                continue
                    else:
                        # No validation, just parse comma-separated lists for plural fields
                        if input_prompt.name.endswith("s"):
                            if "," in value:
                                return [v.strip() for v in value.split(",")]
                            else:
                                return [value.strip()]
                    return value
                self.console.print("[red]This field is required[/red]")
    
    def _get_secret_fields(self, config_model) -> set:
        """Extract SecretStr field names from config model
        
        Args:
            config_model: Pydantic model class for adapter configuration
        
        Returns:
            Set of field names that are marked as SecretStr
        """
        secret_fields = set()
        if config_model:
            for field_name, field_info in config_model.model_fields.items():
                from pydantic import SecretStr
                if field_info.annotation == SecretStr or (
                    hasattr(field_info.annotation, '__origin__') and 
                    field_info.annotation.__origin__ == SecretStr
                ):
                    secret_fields.add(field_name)
        return secret_fields
    
    def _write_platform_yaml(self):
        """Write platform.yaml configuration (excluding secrets)"""
        platform_data = {
            "version": "1.0",
            "platform": self.platform_config,
            "adapters": self.config
        }
        
        # Ensure platform directory exists
        self.platform_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.platform_yaml_path, "w") as f:
            self.yaml.dump(platform_data, f)
    
    def _write_secrets_file(self):
        """Write secrets to ~/.ztc/secrets file (AWS CLI pattern)"""
        if not self.secrets_cache:
            return
        
        import os
        import stat
        import configparser
        
        # Create ~/.ztc directory
        secrets_dir = Path.home() / ".ztc"
        secrets_dir.mkdir(mode=0o700, exist_ok=True)
        
        secrets_file = secrets_dir / "secrets"
        
        # Use ConfigParser to write properly formatted INI file
        config = configparser.ConfigParser()
        
        for adapter_name, secrets in self.secrets_cache.items():
            config[adapter_name] = {}
            for key, value in secrets.items():
                # Handle multi-line values (like RSA keys)
                if "\n" in str(value):
                    # Base64 encode multi-line values for safe storage
                    import base64
                    encoded = base64.b64encode(value.encode()).decode()
                    config[adapter_name][key] = f"base64:{encoded}"
                else:
                    config[adapter_name][key] = str(value)
        
        # Write with ConfigParser to ensure proper formatting
        with open(secrets_file, "w") as f:
            config.write(f, space_around_delimiters=True)
        
        # Set restrictive permissions (600)
        os.chmod(secrets_file, stat.S_IRUSR | stat.S_IWUSR)
    
    def _execute_init_scripts(self, adapter_name: str):
        """Execute init scripts for an adapter after configuration collection
        
        Args:
            adapter_name: Name of the adapter to execute init scripts for
        """
        while True:
            # Merge config with secrets for adapter instantiation
            adapter_config = self.config.get(adapter_name, {}).copy()
            if adapter_name in self.secrets_cache:
                adapter_config.update(self.secrets_cache[adapter_name])
            
            adapter = self.registry.get_adapter(adapter_name, adapter_config)
            
            # Get init scripts from adapter
            init_scripts = adapter.init()
            
            if not init_scripts:
                return
            
            self.console.print(f"\n[bold cyan]Running {adapter_name} init scripts...[/bold cyan]")
            
            executor = ScriptExecutor()
            script_failed = False
            failed_script_desc = None
            error_output = None
            
            for script_ref in init_scripts:
                # Execute script with progress indicator
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    TimeElapsedColumn(),
                    console=self.console
                ) as progress:
                    task = progress.add_task(f"→ {script_ref.description}", total=None)
                    result = executor.execute(script_ref)
                
                if result.exit_code != 0:
                    script_failed = True
                    failed_script_desc = script_ref.description
                    error_output = result.stderr
                    self.console.print(f"[red]✗ Init script failed: {script_ref.description}[/red]")
                    self.console.print(f"[red]STDERR: {result.stderr}[/red]")
                    if result.stdout:
                        self.console.print(f"[yellow]STDOUT: {result.stdout}[/yellow]")
                    self.console.print(f"[dim]Full logs: .zerotouch-cache/init-logs/[/dim]")
                    break
                
                self.console.print(f"[green]✓[/green] {script_ref.description}")
            
            if script_failed:
                # Prompt user to fix and retry
                self.console.print(f"\n[yellow]Script failed: {failed_script_desc}[/yellow]")
                retry = Confirm.ask("Fix the issue and retry configuration for this adapter?", default=True)
                
                if retry:
                    # Re-collect inputs for this adapter
                    self.console.print(f"\n[bold]Reconfigure {adapter_name}[/bold]")
                    adapter_config = self._collect_adapter_inputs(adapter_name)
                    self.config[adapter_name] = adapter_config
                    self._write_platform_yaml()
                    # Loop will retry init scripts
                    continue
                else:
                    # User chose not to retry - raise error to stop init flow
                    raise RuntimeError(f"Init script failed: {failed_script_desc}")
            else:
                # All scripts succeeded
                self.console.print(f"[green]✓[/green] {adapter_name} init complete")
                break
