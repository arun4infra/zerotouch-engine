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
        self.secrets_cache = {}  # Store secrets separately from config
        self.env_vars = {}
        self.platform_yaml_path = Path("platform/platform.yaml")
        self.yaml = YAML()
        self.yaml.default_flow_style = False
        self.yaml.preserve_quotes = True
        self.yaml.width = 4096  # Prevent line wrapping for long values
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
        inputs = adapter.get_required_inputs()
        
        if not inputs:
            return {}
        
        self.console.print(f"\n[bold]Configure {adapter_name}[/bold]")
        
        # Get adapter config model to detect SecretStr fields
        config_model = adapter.config_model
        secret_fields = set()
        if config_model:
            for field_name, field_info in config_model.model_fields.items():
                # Check if field is SecretStr
                from pydantic import SecretStr
                if field_info.annotation == SecretStr or (
                    hasattr(field_info.annotation, '__origin__') and 
                    field_info.annotation.__origin__ == SecretStr
                ):
                    secret_fields.add(field_name)
        
        config = {}
        for input_prompt in inputs:
            # Special handling for GitHub App Private Key - load from .env.global
            if input_prompt.name == "github_app_private_key":
                self.console.print("\n[yellow]GitHub App Private Key must be set in .env.global file[/yellow]")
                self.console.print("[dim]Add this line to .env.global:[/dim]")
                self.console.print('[dim]GIT_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\\n...\\n-----END RSA PRIVATE KEY-----"[/dim]')
                
                while True:
                    ready = Confirm.ask("\nHave you added GIT_APP_PRIVATE_KEY to .env.global?")
                    if not ready:
                        self.console.print("[yellow]Please add the key to .env.global and try again[/yellow]")
                        continue
                    
                    # Reload .env.global to get the key
                    env_file = Path(".env.global")
                    if not env_file.exists():
                        self.console.print("[red].env.global file not found[/red]")
                        continue
                    
                    # Parse .env.global for GIT_APP_PRIVATE_KEY (handles multi-line)
                    key_value = None
                    with open(env_file) as f:
                        content = f.read()
                        # Find GIT_APP_PRIVATE_KEY= and extract until closing quote
                        import re
                        match = re.search(r'GIT_APP_PRIVATE_KEY="(.*?)"', content, re.DOTALL)
                        if match:
                            key_value = match.group(1)
                    
                    if not key_value:
                        self.console.print("[red]GIT_APP_PRIVATE_KEY not found in .env.global[/red]")
                        continue
                    
                    # Validate the key format
                    if not re.match(r"^-----BEGIN RSA PRIVATE KEY-----[\s\S]+-----END RSA PRIVATE KEY-----$", key_value, re.DOTALL):
                        self.console.print("[red]Invalid RSA private key format[/red]")
                        continue
                    
                    # Store in secrets_cache instead of config
                    if adapter_name not in self.secrets_cache:
                        self.secrets_cache[adapter_name] = {}
                    self.secrets_cache[adapter_name][input_prompt.name] = key_value
                    self.console.print("[green]✓[/green] Valid private key loaded from .env.global")
                    break
                continue
            
            # Special handling for tenant_repo_url - show instructions first
            if input_prompt.name == "tenant_repo_url":
                self.console.print(f"\n[yellow]Please create a GitHub repository for tenant configuration:[/yellow]")
                self.console.print("[dim]1. Go to https://github.com/new[/dim]")
                self.console.print("[dim]2. Make it private and initialize with README[/dim]")
                self.console.print("[dim]3. Copy the repository URL[/dim]\n")
                
                while True:
                    repo_url = Prompt.ask(input_prompt.prompt).strip()
                    if not repo_url:
                        self.console.print("[red]Repository URL is required[/red]")
                        continue
                    
                    # Validate URL format
                    import re
                    if not re.match(r"^https://github\.com/[^/]+/[^/]+/?$", repo_url):
                        self.console.print("[red]Invalid GitHub URL format[/red]")
                        self.console.print("[dim]Expected: https://github.com/org/repo[/dim]")
                        continue
                    
                    config[input_prompt.name] = repo_url.rstrip('/')
                    break
                continue
            
            # Skip BGP ASN if BGP not enabled
            if input_prompt.name == "bgp_asn" and not config.get("bgp_enabled", False):
                continue
            
            # Special handling for KSOPS s3_region - extract from s3_endpoint
            if input_prompt.name == "s3_region" and "s3_endpoint" in config:
                import re
                endpoint = config["s3_endpoint"]
                # Extract region from URL like https://fsn1.your-objectstorage.com
                match = re.search(r'https?://([^.]+)\.', endpoint)
                if match:
                    region = match.group(1)
                    config[input_prompt.name] = region
                    self.console.print(f"[dim]{input_prompt.prompt}: {region} (auto-detected from endpoint)[/dim]")
                    continue
            
            # Auto-select if default exists (skip prompt)
            if input_prompt.default is not None:
                config[input_prompt.name] = input_prompt.default
                self.console.print(f"[dim]{input_prompt.prompt}: {input_prompt.default} (auto-selected)[/dim]")
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
                    
                    while True:
                        name = Prompt.ask(f"Server name for {ip} (e.g., cp01, worker01)").strip()
                        if name:
                            break
                        self.console.print("[red]Server name is required[/red]")
                    
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
                        # Only strip leading/trailing whitespace, preserve internal newlines for keys
                        value = value.strip()
                        # Validate password fields if pattern provided
                        if input_prompt.validation:
                            import re
                            # For RSA keys, accept both single-line and multi-line format
                            if "RSA PRIVATE KEY" in input_prompt.validation:
                                # Normalize: if single line, add newlines after headers
                                if "\\n" not in value and "\n" not in value:
                                    # Single-line format - add newlines
                                    value = value.replace("-----BEGIN RSA PRIVATE KEY-----", "-----BEGIN RSA PRIVATE KEY-----\n")
                                    value = value.replace("-----END RSA PRIVATE KEY-----", "\n-----END RSA PRIVATE KEY-----")
                            
                            if not re.match(input_prompt.validation, value, re.DOTALL):
                                self.console.print(f"[red]Invalid format. {input_prompt.help_text}[/red]")
                                continue
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
                        value = value.strip()
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
            
            # Store secrets separately from config
            if input_prompt.name in secret_fields:
                if adapter_name not in self.secrets_cache:
                    self.secrets_cache[adapter_name] = {}
                self.secrets_cache[adapter_name][input_prompt.name] = value
            else:
                config[input_prompt.name] = value
        
        return config
    
    def _write_platform_yaml(self):
        """Write platform.yaml configuration (excluding secrets)"""
        platform_data = {
            "version": "1.0",
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
        
        # Create ~/.ztc directory
        secrets_dir = Path.home() / ".ztc"
        secrets_dir.mkdir(mode=0o700, exist_ok=True)
        
        secrets_file = secrets_dir / "secrets"
        
        # Write secrets in INI format (like AWS credentials)
        with open(secrets_file, "w") as f:
            for adapter_name, secrets in self.secrets_cache.items():
                f.write(f"[{adapter_name}]\n")
                for key, value in secrets.items():
                    # Handle multi-line values (like RSA keys)
                    if "\n" in str(value):
                        # Base64 encode multi-line values for safe storage
                        import base64
                        encoded = base64.b64encode(value.encode()).decode()
                        f.write(f"{key} = base64:{encoded}\n")
                    else:
                        f.write(f"{key} = {value}\n")
                f.write("\n")
        
        # Set file permissions to 600 (user read/write only)
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
