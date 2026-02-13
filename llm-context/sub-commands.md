# Adapter CLI Subcommands Pattern

## Overview

ZTC adapters can optionally expose tool-specific CLI commands as subcommands under their **category namespace** (e.g., `ztc <category> <command>`). This pattern maintains separation between:

- **Lifecycle commands**: Bootstrap, validation, rendering (handled by PlatformAdapter)
- **Tool commands**: User-facing utilities specific to the adapter's domain (handled by adapter directly)

## Design Principles

1. **PlatformAdapter remains lifecycle-focused**: Base adapter interface only handles render pipeline and lifecycle scripts
2. **Optional CLI extension**: Adapters opt-in to CLI commands via mixin pattern
3. **Direct routing**: Tool commands route directly to adapter methods, bypassing lifecycle
4. **Category-based namespacing**: Commands use category names (e.g., `secret`, `network`), not tool names (e.g., `ksops`, `cilium`)
5. **Single category selection**: Users select one adapter per category; CLI commands route to the selected adapter
6. **Encapsulation**: Each adapter owns its category's CLI namespace and command implementations

## Category-Based CLI Namespacing

### Rationale

CLI commands must use **category names** rather than specific tool names to support adapter interchangeability:

- Users select one adapter per category from a catalog (e.g., KSOPS vs Sealed Secrets for secrets management)
- CLI commands remain consistent regardless of which adapter is selected
- Switching adapters doesn't break user workflows or scripts

### Examples

**Correct (Category-based):**
```bash
ztc secret init-secrets production      # Works with KSOPS, Sealed Secrets, or any secrets adapter
ztc network status                      # Works with Cilium, Calico, or any network adapter
ztc storage create-volume               # Works with any storage adapter
```

**Incorrect (Tool-specific):**
```bash
ztc ksops init-secrets production       # Breaks if user switches to Sealed Secrets
ztc cilium status                       # Breaks if user switches to Calico
```

### Category Mapping

Adapters declare their category via `selection_group` in `adapter.yaml`:

```yaml
# adapter.yaml
name: ksops
selection_group: secrets_management     # Category: secrets
phase: secrets

# Another example
name: sealed-secrets
selection_group: secrets_management     # Same category: secrets
phase: secrets
```

CLI registration uses the category name, not the adapter name.

## Architecture

### Base Adapter (Lifecycle Only)

```python
# ztc/adapters/base.py
class PlatformAdapter:
    """Base adapter - lifecycle operations only"""
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Scripts for adapter bootstrap phase"""
        pass
    
    def validation_scripts(self) -> List[ScriptReference]:
        """Scripts for adapter validation phase"""
        pass
    
    async def render(self, ctx: ContextSnapshot) -> AdapterOutput:
        """Generate manifests and capability data"""
        pass
```

### CLI Extension Mixin

```python
# ztc/adapters/base.py
class CLIExtension:
    """Optional mixin for adapters that provide CLI commands"""
    
    def get_cli_app(self) -> Optional[typer.Typer]:
        """Return Typer instance with adapter-specific commands
        
        Returns:
            typer.Typer instance with registered commands, or None if no CLI commands
        """
        return None
```

### Adapter Implementation

```python
# ztc/adapters/ksops/adapter.py
class KSOPSAdapter(PlatformAdapter, CLIExtension):
    """KSOPS adapter with both lifecycle and CLI commands"""
    
    # Lifecycle methods
    def bootstrap_scripts(self) -> List[ScriptReference]:
        return [...]
    
    # CLI extension - commands registered under "secret" category
    def get_cli_app(self) -> typer.Typer:
        """Register secrets management CLI commands
        
        Note: Commands are registered under category name "secret",
        not adapter name "ksops". This allows users to switch between
        KSOPS, Sealed Secrets, or other secrets adapters without
        breaking CLI workflows.
        """
        app = typer.Typer(help="Secrets management tools")
        
        app.command(name="init-secrets")(self.init_secrets_command)
        app.command(name="create-dot-env")(self.create_dot_env_command)
        app.command(name="encrypt-secret")(self.encrypt_secret_command)
        app.command(name="rotate-keys")(self.rotate_keys_command)
        
        return app
    
    # Command handlers
    def init_secrets_command(self, env: str):
        """Initialize environment-specific secrets"""
        # Extract scripts, generate context, execute
        pass
    
    def create_dot_env_command(self):
        """Generate .env from encrypted secrets"""
        pass
    
    def encrypt_secret_command(self, file: str):
        """Encrypt individual secret file"""
        pass
    
    def rotate_keys_command(self):
        """Rotate encryption keys and re-encrypt secrets"""
        pass
```

### Category Name Resolution

```python
# ztc/adapters/base.py
class CLIExtension:
    """Optional mixin for adapters that provide CLI commands"""
    
    def get_cli_category(self) -> str:
        """Return CLI category name for this adapter
        
        Derives category from selection_group in adapter.yaml:
        - secrets_management -> "secret"
        - network_plugin -> "network"
        - storage_provider -> "storage"
        
        Returns:
            Category name for CLI namespace
        """
        metadata = self.load_metadata()
        selection_group = metadata.get("selection_group", "")
        
        # Map selection_group to CLI category
        category_map = {
            "secrets_management": "secret",
            "network_plugin": "network",
            "storage_provider": "storage",
            "os_provider": "os",
            "cloud_provider": "cloud"
        }
        
        return category_map.get(selection_group, selection_group)
    
    def get_cli_app(self) -> Optional[typer.Typer]:
        """Return Typer instance with adapter-specific commands"""
        return None
```

## CLI Registration

### Dynamic Subcommand Discovery

```python
# ztc/cli.py
from ztc.adapters.base import CLIExtension
from ztc.registry.adapter_registry import AdapterRegistry

app = typer.Typer(name="ztc")

def register_adapter_subcommands():
    """Discover and register adapter CLI extensions
    
    Registers commands under category names, not adapter names.
    Only one adapter per category can provide CLI commands.
    """
    registry = AdapterRegistry()
    registry.discover_adapters()
    
    # Load platform.yaml to determine selected adapters
    platform_config = load_platform_config()
    selected_adapters = platform_config.get("adapters", {})
    
    # Track registered categories to prevent conflicts
    registered_categories = {}
    
    for adapter_name in selected_adapters.keys():
        adapter_class = registry.get_adapter_class(adapter_name)
        
        # Check if adapter implements CLI extension
        if issubclass(adapter_class, CLIExtension):
            # Instantiate with config for CLI registration
            adapter_config = selected_adapters[adapter_name]
            adapter_instance = adapter_class(adapter_config)
            
            # Get category name (not adapter name)
            category = adapter_instance.get_cli_category()
            cli_app = adapter_instance.get_cli_app()
            
            if cli_app:
                # Prevent multiple adapters from same category
                if category in registered_categories:
                    raise ValueError(
                        f"Category '{category}' CLI already registered by "
                        f"'{registered_categories[category]}'. "
                        f"Cannot register '{adapter_name}'."
                    )
                
                # Register under category name
                app.add_typer(
                    cli_app,
                    name=category,  # Use category, not adapter_name
                    help=f"{category.title()} management tools"
                )
                
                registered_categories[category] = adapter_name

# Register on CLI startup
register_adapter_subcommands()
```

## Usage Examples

### User Perspective

```bash
# Lifecycle commands (global)
ztc render
ztc bootstrap
ztc validate

# Category-based tool commands (namespaced by category, not adapter)
ztc secret init-secrets production      # Routes to selected secrets adapter (KSOPS, Sealed Secrets, etc.)
ztc secret create-dot-env                # Same category, different command
ztc secret encrypt-secret config.yaml   # Encrypt individual file
ztc secret rotate-keys                   # Rotate encryption keys

ztc network status                       # Routes to selected network adapter (Cilium, Calico, etc.)
ztc network apply-policy policy.yaml     # Apply network policy

ztc storage create-volume 100Gi          # Routes to selected storage adapter
```

### Help Output

```bash
$ ztc --help
Usage: ztc [OPTIONS] COMMAND [ARGS]...

Commands:
  render      Generate platform artifacts
  bootstrap   Execute bootstrap pipeline
  validate    Validate generated artifacts
  secret      Secrets management tools
  network     Network management tools
  storage     Storage management tools

$ ztc secret --help
Usage: ztc secret [OPTIONS] COMMAND [ARGS]...

  Secrets management tools

Commands:
  init-secrets    Initialize environment-specific secrets
  create-dot-env  Generate .env from encrypted secrets
  encrypt-secret  Encrypt individual secret file
  rotate-keys     Rotate encryption keys and re-encrypt secrets

Note: Commands route to the selected secrets adapter (currently: ksops)
```

### Adapter Switching Example

```yaml
# platform.yaml - Using KSOPS
adapters:
  ksops:
    version: v1.0.0
    # ... config

# CLI commands work
$ ztc secret init-secrets production
✓ Secrets initialized (using KSOPS)
```

```yaml
# platform.yaml - Switched to Sealed Secrets
adapters:
  sealed-secrets:
    version: v1.0.0
    # ... config

# Same CLI commands still work
$ ztc secret init-secrets production
✓ Secrets initialized (using Sealed Secrets)
```

**Key Point**: User workflows remain unchanged when switching adapters within the same category.

## Implementation Guidelines

### When to Use CLI Extension

Adapters should implement CLI extension when they provide:

- **User-facing utilities**: Tools operators use directly (not part of bootstrap)
- **Manual operations**: Break-glass commands, debugging tools
- **Resource management**: Initialization, cleanup, status checks
- **Category-specific operations**: Secret management, network policies, storage volumes

### When NOT to Use CLI Extension

Do not use CLI extension for:

- **Lifecycle operations**: Bootstrap, validation, rendering (use PlatformAdapter methods)
- **Internal operations**: Called only by other adapters or engine
- **One-time setup**: Handled by `ztc init` interactive prompts

### Category Consistency Requirements

All adapters in the same category **must provide compatible CLI commands**:

**Example: Secrets Management Category**

Both KSOPS and Sealed Secrets must implement:
- `init-secrets <env>` - Initialize secrets for environment
- `create-dot-env` - Generate .env file
- `encrypt-secret <file>` - Encrypt a secret file
- `rotate-keys` - Rotate encryption keys

This ensures users can switch adapters without relearning commands.

### Command Naming Conventions

- Use **category-agnostic names**: `init-secrets`, not `init-ksops-secrets`
- Use **verb-noun pattern**: `create-volume`, `apply-policy`, `rotate-keys`
- Use **kebab-case**: `init-secrets`, not `init_secrets` or `initSecrets`
- Avoid **tool-specific terminology**: Use generic terms that apply to all adapters in category

### Command Handler Pattern

```python
def command_handler(self, arg1: str, arg2: bool = False):
    """Command handler implementation
    
    Handlers should:
    1. Extract required scripts from adapter package
    2. Generate context JSON from arguments
    3. Execute script with context file
    4. Handle errors and display results
    """
    from ztc.engine.script_executor import ScriptExecutor
    
    # 1. Get script reference
    script_ref = ScriptReference(
        package="ztc.adapters.my_adapter.scripts.tools",
        resource="init.sh",
        description="Initialize resources"
    )
    
    # 2. Generate context data
    context_data = {
        "arg1": arg1,
        "arg2": arg2,
        "config_field": self.config.get("field")
    }
    
    # 3. Execute script
    executor = ScriptExecutor()
    result = executor.execute(script_ref, context_data)
    
    # 4. Display results
    if result.exit_code == 0:
        console.print("[green]✓[/green] Command completed")
    else:
        console.print(f"[red]✗[/red] Command failed: {result.stderr}")
        raise typer.Exit(1)
```

## Typer Integration

### Native Typer Features

ZTC leverages Typer's native `add_typer()` method for subcommand registration:

```python
# Typer supports dynamic subcommand groups
main_app = typer.Typer()
sub_app = typer.Typer()

# Register subcommand group at runtime
main_app.add_typer(sub_app, name="subcommand")
```

### No Plugin System Required

Typer does not have a native plugin/hook system. ZTC implements adapter CLI discovery using:

- **Mixin pattern**: `CLIExtension` interface
- **Registry discovery**: Scan adapters at startup
- **Dynamic registration**: Call `add_typer()` for each adapter with CLI commands

## Testing

### Unit Tests

```python
def test_adapter_cli_registration():
    """Test adapter registers CLI commands"""
    adapter = MyAdapter({})
    cli_app = adapter.get_cli_app()
    
    assert cli_app is not None
    assert "init" in [cmd.name for cmd in cli_app.registered_commands]

def test_command_handler():
    """Test command handler execution"""
    adapter = MyAdapter({"field": "value"})
    
    # Mock script executor
    with patch('ztc.engine.script_executor.ScriptExecutor') as mock_executor:
        mock_executor.return_value.execute.return_value = MockResult(exit_code=0)
        
        adapter.init_command("production")
        
        mock_executor.return_value.execute.assert_called_once()
```

### Integration Tests

```python
def test_cli_subcommand_execution():
    """Test full CLI subcommand execution"""
    from typer.testing import CliRunner
    
    runner = CliRunner()
    result = runner.invoke(app, ["my-adapter", "init", "production"])
    
    assert result.exit_code == 0
    assert "Command completed" in result.stdout
```

## Best Practices

1. **Use category names, not adapter names**: Commands must work across all adapters in a category
2. **Keep commands focused**: Each command should do one thing well
3. **Use context files**: Pass data to scripts via JSON context (not CLI args)
4. **Provide help text**: Document all commands and arguments
5. **Handle errors gracefully**: Display actionable error messages
6. **Validate inputs**: Use Typer's type hints and validation
7. **Maintain separation**: CLI commands should not call lifecycle methods directly
8. **Test independently**: CLI commands should be testable without full bootstrap
9. **Document category contract**: Clearly specify which commands all adapters in category must implement
10. **Coordinate with category peers**: Ensure command compatibility with other adapters in same category

## Category Command Contracts

### Secrets Management Category (`secret`)

Required commands all secrets adapters must implement:

```bash
ztc secret init-secrets <env>           # Initialize environment secrets
ztc secret create-dot-env                # Generate .env from encrypted secrets
ztc secret encrypt-secret <file>         # Encrypt individual secret file
ztc secret rotate-keys                   # Rotate encryption keys
```

### Network Management Category (`network`)

Required commands all network adapters must implement:

```bash
ztc network status                       # Check network status
ztc network apply-policy <file>          # Apply network policy
ztc network troubleshoot                 # Run network diagnostics
```

### Storage Management Category (`storage`)

Required commands all storage adapters must implement:

```bash
ztc storage create-volume <size>         # Create storage volume
ztc storage list-volumes                 # List all volumes
ztc storage delete-volume <name>         # Delete volume
```

**Note**: Categories should document their command contracts in `docs/categories/<category>.md`.

## Migration Path

For existing adapters without CLI commands:

1. Adapter continues to work (CLI extension is optional)
2. Add `CLIExtension` mixin when tool commands are needed
3. Implement `get_cli_category()` to return category name
4. Implement `get_cli_app()` with category-compatible commands
5. Coordinate with other adapters in same category to ensure command compatibility

No breaking changes to existing adapters.

### Adding CLI to Existing Adapter

```python
# Before: Adapter without CLI
class MyAdapter(PlatformAdapter):
    def bootstrap_scripts(self): ...

# After: Adapter with category-based CLI
class MyAdapter(PlatformAdapter, CLIExtension):
    def bootstrap_scripts(self): ...
    
    def get_cli_category(self) -> str:
        return "secret"  # Category from selection_group
    
    def get_cli_app(self) -> typer.Typer:
        app = typer.Typer()
        # Implement category-standard commands
        app.command()(self.init_secrets)
        app.command()(self.create_dot_env)
        return app
```

## Conflict Resolution

### Multiple Adapters in Same Category

Platform configuration can only have **one adapter per category**:

```yaml
# Valid: One secrets adapter
adapters:
  ksops:
    version: v1.0.0

# Invalid: Multiple secrets adapters
adapters:
  ksops:
    version: v1.0.0
  sealed-secrets:  # ERROR: Conflicts with ksops (both in secrets_management category)
    version: v1.0.0
```

CLI registration enforces this constraint and raises error if multiple adapters from same category attempt to register commands.
