# Design: ZTC Phase 1 - Multi-Adapter Foundation

## 1. Architecture Overview

The ZTC Engine transforms user intent into executable bootstrap artifacts through a three-adapter system (Hetzner, Cilium, Talos). The CLI provides progressive input collection via Typer + Rich, generating `platform.yaml` from interactive prompts. Adapters embed scripts and Jinja2 templates, generating machine configs and pipeline stages compatible with the existing `stage-executor.sh` pattern.

### 1.1 High-Level Flow

```
User Intent (Interactive Prompts)
    ↓
platform.yaml (Generated Config)
    ↓
ZTC Engine (Python)
    ↓
Adapter Resolution (Phase + Capability-Based)
    ↓
Hetzner Adapter → Cilium Adapter → Talos Adapter
    ↓
Generated Artifacts (Configs + Pipeline YAML)
    ↓
Git Commit
    ↓
ztc bootstrap → stage-executor.sh → Kubernetes Cluster
```

### 1.2 Core Components

```
# ZTC CLI (Binary Distribution)
ztc (embedded adapters + templates + scripts)
├── adapters/                        # Embedded in binary (3 adapters)
│   ├── hetzner/
│   │   ├── adapter.yaml             # Metadata
│   │   ├── adapter.py               # Render logic
│   │   ├── schema.json              # Config validation
│   │   ├── output-schema.json       # Output contract
│   │   └── scripts/                 # Embedded scripts
│   │       ├── enable-rescue-mode.sh
│   │       └── api-helper.sh
│   ├── cilium/
│   │   ├── adapter.yaml
│   │   ├── adapter.py
│   │   ├── schema.json
│   │   ├── output-schema.json
│   │   ├── templates/
│   │   │   └── manifests.yaml.j2
│   │   └── scripts/
│   │       ├── wait-cilium.sh
│   │       └── wait-gateway-api.sh
│   └── talos/
│       ├── adapter.yaml
│       ├── adapter.py
│       ├── schema.json
│       ├── output-schema.json
│       ├── templates/
│       │   ├── controlplane.yaml.j2
│       │   ├── worker.yaml.j2
│       │   └── talosconfig.j2
│       └── scripts/
│           ├── 02-embed-network-manifests.sh
│           ├── 03-install-talos.sh
│           ├── 04-bootstrap-talos.sh
│           └── 05-add-worker-nodes.sh
├── versions.yaml                    # Embedded version matrix
└── LOGIC_HASH                       # SHA256 of embedded adapters

# User Repository (Generated Structure)
user-repo/
├── platform.yaml                    # [USER OWNED] Generated from prompts
├── platform/
│   ├── generated/                   # [ENGINE OWNED] Wiped on render
│   │   ├── network/
│   │   │   └── cilium/
│   │   │       └── manifests.yaml
│   │   └── os/
│   │       └── talos/
│   │           ├── nodes/
│   │           │   ├── cp01-main/
│   │           │   │   └── config.yaml
│   │           │   └── worker01/
│   │           │       └── config.yaml
│   │           └── talosconfig
│   └── lock.json                    # [ENGINE OWNED] Render metadata
├── bootstrap/
│   └── pipeline/
│       └── production.yaml          # [ENGINE OWNED] Generated pipeline
└── .zerotouch-cache/                # [GITIGNORED] Runtime state
    ├── workspace/                   # Temp render workspace
    └── bootstrap-stage-cache.json   # Stage completion tracking
```

**Key Principles:**
- **CLI-First**: All adapter code embedded in `ztc` binary
- **Progressive Input**: Wizard-style prompts with resume capability
- **Script Embedding**: User never sees installation scripts (embedded in adapters)
- **Stage Compatibility**: Generated pipeline YAML compatible with existing `stage-executor.sh`
- **Atomic Render**: All-or-nothing artifact generation with rollback
- **Lock File Safety**: Prevents drift between render and bootstrap

## 2. CLI Architecture (Typer + Rich)

### 2.1 Command Structure

```python
# ztc/cli.py
import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.progress import Progress
from rich.table import Table

app = typer.Typer(
    name="ztc",
    help="ZeroTouch Composition Engine - Bare-metal Kubernetes bootstrap",
    add_completion=False
)
console = Console()

@app.command()
def init(
    resume: bool = typer.Option(False, "--resume", help="Resume from existing platform.yaml")
):
    """Initialize platform configuration via interactive prompts"""
    # Progressive input collection workflow
    
@app.command()
def render(
    debug: bool = typer.Option(False, "--debug", help="Preserve workspace on failure"),
    partial: Optional[List[str]] = typer.Option(None, "--partial", help="Render specific adapters")
):
    """Generate platform artifacts from platform.yaml"""
    # Render pipeline execution
    
@app.command()
def validate():
    """Validate generated artifacts against lock file"""
    # Lock file validation
    
@app.command()
def bootstrap(
    env: str = typer.Option("production", "--env", help="Target environment"),
    skip_cache: bool = typer.Option(False, "--skip-cache", help="Ignore stage cache")
):
    """Execute bootstrap pipeline"""
    # Bootstrap execution via stage-executor.sh pattern

@app.command()
def eject(
    env: str = typer.Option("production", "--env", help="Target environment"),
    output_dir: Path = typer.Option("debug", "--output", help="Output directory for ejected artifacts")
):
    """Eject scripts and pipeline for manual debugging (break-glass mode)
    
    Extracts all embedded scripts, context files, and pipeline.yaml to a debug directory,
    allowing operators to inspect and manually execute bootstrap logic when CLI fails.
    
    Use cases:
    - Debugging failed bootstrap stages
    - Manual intervention during cluster setup
    - Understanding script execution flow
    - Customizing scripts for edge cases
    """
    from ztc.workflows.eject import EjectWorkflow
    
    workflow = EjectWorkflow(console, output_dir, env)
    workflow.run()

@app.command()
def vacuum():
    """Clean up stale temporary directories from crashed runs (safety net)
    
    Removes ztc-secure-* directories older than 60 minutes from /tmp.
    This handles cases where SIGKILL (9) prevented normal cleanup.
    
    Run automatically on CLI startup or manually after crashes.
    """
    from ztc.utils.vacuum import VacuumCommand
    
    vacuum_cmd = VacuumCommand(console)
    vacuum_cmd.execute()

@app.command()
def version():
    """Display CLI version and embedded adapter versions"""
    # Version information display
```

### 2.2 Progressive Input Collection Workflow with Dynamic Registry

```python
# ztc/registry/groups.py
from dataclasses import dataclass
from typing import List

@dataclass
class SelectionGroup:
    """Data-driven selection group for exclusive adapter categories"""
    name: str                    # e.g., "cloud_provider"
    prompt: str                  # User-facing prompt text
    options: List[str]           # Available adapter choices
    default: str                 # Default selection
    help_text: str = ""          # Optional help text

def build_selection_groups(registry: 'AdapterRegistry') -> List[SelectionGroup]:
    """Dynamically build selection groups from adapter registry metadata
    
    Scales to 19+ adapters without modifying workflow code.
    Adapters declare their selection_group in adapter.yaml metadata.
    """
    groups = {}
    
    for adapter_name in registry.list_adapters():
        adapter = registry.get_adapter(adapter_name)
        meta = adapter.load_metadata()
        
        # Use explicit selection_group or fall back to phase
        group_name = meta.get("selection_group", meta["phase"])
        
        if group_name not in groups:
            groups[group_name] = {
                "name": group_name,
                "prompt": meta.get("group_prompt", f"Select {group_name}"),
                "options": [],
                "default": None,
                "help_text": meta.get("group_help", "")
            }
        
        groups[group_name]["options"].append(adapter_name)
        
        # Set default if adapter declares it
        if meta.get("is_default", False):
            groups[group_name]["default"] = adapter_name
    
    # Convert to SelectionGroup objects
    selection_groups = []
    for group_data in groups.values():
        # Ensure default is set (use first option if not declared)
        if not group_data["default"]:
            group_data["default"] = group_data["options"][0]
        
        selection_groups.append(SelectionGroup(**group_data))
    
    return selection_groups

# ztc/workflows/init.py
from rich.prompt import Prompt, Confirm
from rich.table import Table
from ztc.registry.groups import SelectionGroup, build_selection_groups

class InitWorkflow:
    def __init__(self, console: Console, adapter_registry: AdapterRegistry):
        self.console = console
        self.registry = adapter_registry
        self.config = {}
        
        # Dynamically build selection groups from registry (no hardcoded lists)
        self.selection_groups = build_selection_groups(adapter_registry)
    
    def run(self, resume: bool = False) -> Dict[str, Any]:
        """Execute progressive input collection workflow"""
        
        # Step 1: Load existing config if resuming
        if resume and Path("platform.yaml").exists():
            self.config = self.load_existing_config()
            self.console.print("[green]✓[/green] Loaded existing platform.yaml")
        
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
        
        # Step 9: Display summary
        self.display_summary()
        
        return self.config
    
    def handle_group_selection(self, group: SelectionGroup) -> str:
        """Handle exclusive selection with generic cleanup logic"""
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
    
    def validate_downstream_adapters(self, changed_adapter: PlatformAdapter):
        """Validate downstream adapters when upstream context changes (differential)
        
        Uses get_invalid_fields() to preserve valid config and only re-prompt invalid fields.
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
    
    def collect_adapter_inputs(self, adapter: PlatformAdapter):
        """Collect inputs for specific adapter with Pydantic validation"""
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
            adapter_config = self.config[adapter.name]  # Required field
            if (input_def.name in adapter_config 
                and input_def.name not in invalid_fields):
                continue
            
            # Pre-fill with existing value if available (even if invalid)
            existing_value = adapter_config.get(input_def.name)  # Legitimate: checking if key exists
            if existing_value and input_def.name in invalid_fields:
                self.console.print(f"[red]Invalid value:[/red] {existing_value}")
            
            value = self.prompt_input(input_def, default_override=existing_value)
            self.config.setdefault(adapter.name, {})[input_def.name] = value
    
    def prompt_input(self, input_def: InputPrompt) -> Any:
        """Prompt for single input with validation"""
        if input_def.type == "choice":
            return Prompt.ask(
                input_def.prompt,
                choices=input_def.choices,
                default=input_def.default
            )
        elif input_def.type == "boolean":
            return Confirm.ask(input_def.prompt, default=input_def.default)
        elif input_def.type == "password":
            return Prompt.ask(input_def.prompt, password=True)
        else:
            return Prompt.ask(input_def.prompt, default=input_def.default)
    
    def display_summary(self):
        """Display configuration summary table"""
        table = Table(title="Platform Configuration Summary")
        table.add_column("Adapter", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Configuration", style="yellow")
        
        for adapter_name, adapter_config in self.config.items():
            if isinstance(adapter_config, dict):
                version = adapter_config["version"]  # Required field
                config_str = ", ".join(f"{k}={v}" for k, v in adapter_config.items() if k != "version")
                table.add_row(adapter_name, version, config_str)
        
        self.console.print(table)
```

### 2.3 Version Selection with Defaults

```python
# ztc/adapters/base.py
class PlatformAdapter:
    def get_version_prompt(self) -> InputPrompt:
        """Generate version selection prompt with defaults"""
        metadata = self.load_metadata()
        
        return InputPrompt(
            name="version",
            prompt=f"Select {self.name} version",
            type="choice",
            choices=metadata["supported_versions"],
            default=metadata["default_version"],
            help_text=f"Recommended: {metadata['default_version']}"
        )
```

## 3. Adapter Contract

### 3.0 Capability Interface Contracts

To ensure type safety and prevent runtime errors as the system scales to 19 adapters, all capability data must conform to strict Pydantic models with enum-based lookups.

```python
# ztc/interfaces/capabilities.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Type
from enum import StrEnum

class CNIArtifacts(BaseModel):
    """Strict contract for 'cni' capability providers (Cilium, Calico, etc.)"""
    manifests: str = Field(..., description="YAML manifests for CNI installation")
    cni_conf: Optional[str] = Field(None, description="CNI configuration file content")
    ready: bool = Field(False, description="Whether CNI is operational")

class KubernetesAPICapability(BaseModel):
    """Strict contract for 'kubernetes-api' capability providers (Talos, kubeadm, etc.)"""
    cluster_endpoint: str = Field(..., regex=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$")
    kubeconfig_path: str
    version: str = Field(..., regex=r"^>=\d+\.\d+$")

class CloudInfrastructureCapability(BaseModel):
    """Strict contract for 'cloud-infrastructure' capability providers (Hetzner, AWS, etc.)"""
    provider: str
    server_ids: Dict[str, str]  # IP -> Server ID mapping
    rescue_mode_enabled: bool

class GatewayAPICapability(BaseModel):
    """Strict contract for 'gateway-api' capability providers"""
    version: str
    crds_embedded: bool

# Enum-based capability registry (Python 3.11+ StrEnum for type safety)
class Capability(StrEnum):
    """Type-safe capability identifiers (prevents typos like 'CNI' vs 'cni')"""
    CNI = "cni"
    KUBERNETES_API = "kubernetes-api"
    CLOUD_INFRASTRUCTURE = "cloud-infrastructure"
    GATEWAY_API = "gateway-api"

# Bind capability enums to Pydantic models
CAPABILITY_CONTRACTS: Dict[Capability, Type[BaseModel]] = {
    Capability.CNI: CNIArtifacts,
    Capability.KUBERNETES_API: KubernetesAPICapability,
    Capability.CLOUD_INFRASTRUCTURE: CloudInfrastructureCapability,
    Capability.GATEWAY_API: GatewayAPICapability,
}
```

### 3.1 Adapter Metadata (adapter.yaml)

```yaml
name: talos
version: 1.0.0
phase: foundation                    # foundation, networking, platform, services
selection_group: os                  # For dynamic UI grouping (cloud_provider, network_tool, os)
is_default: true                     # Default selection in group
group_prompt: "Select operating system"
group_help: "Base OS for Kubernetes nodes"
provides:                            # Capabilities exposed
  - capability: kubernetes-api
    version: ">=1.28"
requires:                            # Capability dependencies
  - capability: cloud-infrastructure
    version: v1.0
  - capability: cni
    version: v1.0
supported_versions:                  # User-selectable versions
  - v1.10.x
  - v1.11.5
default_version: v1.11.5             # Recommended version
config_schema: schema.json
output_schema: output-schema.json
```

### 3.2 Adapter Interface with Lifecycle Hooks and Validation

```python
# ztc/adapters/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class InputPrompt:
    """Definition for interactive user input"""
    name: str
    prompt: str
    type: str  # choice, boolean, string, password, integer
    choices: Optional[List[str]] = None
    default: Optional[Any] = None
    validation: Optional[str] = None  # Regex pattern
    help_text: Optional[str] = None

@dataclass
class ScriptReference:
    """Reference to embedded script with static validation and context data
    
    Uses importlib.resources to validate script existence at class load time,
    preventing runtime FileNotFoundError during critical bootstrap phase.
    
    Context data is passed via JSON file instead of CLI args for safety:
    - Avoids shell escaping issues with special characters
    - Supports complex data structures (arrays, nested objects)
    - Scripts read via $ZTC_CONTEXT_FILE environment variable
    """
    package: str                      # e.g., "ztc.adapters.talos.scripts"
    resource: 'ScriptEnum'            # Enum value (e.g., TalosScripts.INSTALL)
    description: str
    timeout: int = 300                # seconds
    context_data: Dict[str, Any] = None  # Data passed via context.json (replaces args)
    args: List[str] = None            # Deprecated: use context_data instead
    
    def __post_init__(self):
        """Validate script existence immediately upon instantiation"""
        import importlib.resources
        
        # Validate resource exists in package
        try:
            files = importlib.resources.files(self.package)
            script_path = files / self.resource.value
            
            if not script_path.is_file():
                raise FileNotFoundError(
                    f"Script '{self.resource.value}' not found in package '{self.package}'. "
                    f"Check adapter scripts directory."
                )
        except (ModuleNotFoundError, AttributeError) as e:
            raise FileNotFoundError(
                f"Package '{self.package}' not found or inaccessible: {e}"
            )
        
        # Generate URI for backward compatibility
        adapter_name = self.package.split('.')[-2]  # Extract from "ztc.adapters.talos.scripts"
        self.uri = f"{adapter_name}://{self.resource.value}"
        
        # Warn if using deprecated args
        if self.args and self.context_data:
            import warnings
            warnings.warn(
                f"Script '{self.resource.value}' uses both args and context_data. "
                "Prefer context_data for safety.",
                DeprecationWarning
            )

@dataclass
class PipelineStage:
    """Stage definition for bootstrap pipeline"""
    name: str
    description: str
    script: str  # URI to embedded script
    cache_key: Optional[str]  # None = always run
    required: bool = True
    args: List[str] = None
    skip_if_empty: Optional[str] = None  # Env var name
    phase: str = "foundation"
    barrier: str = "local"  # local, cluster_installed, cluster_accessible, cni_ready

@dataclass
class AdapterOutput:
    """Output from adapter render"""
    manifests: Dict[str, str]      # filename → content
    stages: List[PipelineStage]    # Pipeline stage definitions
    env_vars: Dict[str, str]       # Environment variables
    capabilities: Dict[str, Any]   # Capability-based data (e.g., {"cni": CNIArtifacts})
    data: Dict[str, Any]           # Legacy: Output data for downstream adapters (deprecated)

class PlatformAdapter(ABC):
    def __init__(self, config: Dict[str, Any], jinja_env: Environment = None):
        self.config = config
        self.name = self.load_metadata()["name"]
        self.phase = self.load_metadata()["phase"]
        self._jinja_env = jinja_env  # Shared environment from Engine
    
    @property
    @abstractmethod
    def config_model(self) -> Type[BaseModel]:
        """Return Pydantic model for config validation"""
        pass
    
    @property
    def jinja_env(self) -> Environment:
        """Access shared Jinja2 environment (provided by Engine)
        
        Note: Environment is shared across all adapters for performance.
        Templates are isolated via adapter-specific path prefixes.
        """
        if self._jinja_env is None:
            raise RuntimeError(
                f"Adapter '{self.name}' accessed jinja_env before Engine initialization. "
                "Jinja environment must be provided via constructor."
            )
        return self._jinja_env
    
    def get_template_dir(self) -> Path:
        """Return adapter's template directory for Engine loader configuration"""
        return Path(__file__).parent / "templates"
    
    @abstractmethod
    def get_required_inputs(self) -> List[InputPrompt]:
        """Return list of interactive prompts for user input collection"""
        pass
    
    def validate_upstream_context(self, current_config: Dict, full_platform_context: Dict) -> bool:
        """Validate if current adapter config is still valid given platform context changes
        
        Args:
            current_config: This adapter's current configuration
            full_platform_context: Complete platform.yaml context
        
        Returns:
            True if config is valid, False if it needs re-prompting
        
        Example:
            Cilium adapter checks if OS is still Talos (for manifest embedding).
            If OS changed to Ubuntu, return False to force re-configuration.
        
        Note:
            Deprecated in favor of get_invalid_fields() for differential validation.
        """
        return True  # Default: always valid (override in subclasses)
    
    def get_invalid_fields(self, current_config: Dict, full_platform_context: Dict) -> List[str]:
        """Return specific fields that are invalid due to upstream context changes
        
        Args:
            current_config: This adapter's current configuration
            full_platform_context: Complete platform.yaml context
        
        Returns:
            List of field names that need re-prompting (empty = all valid)
        
        Example:
            If OS changes from Talos to Ubuntu, Cilium's "embedded_mode" becomes invalid.
            Return ["embedded_mode"] to re-prompt only that field, keeping other config.
        
        Benefits:
            - Preserves valid configuration (better UX than deleting entire config)
            - User only re-enters invalid fields, not entire adapter config
        """
        return []  # Default: no invalid fields (override in subclasses)
    
    @abstractmethod
    def pre_work_scripts(self) -> List[ScriptReference]:
        """Return installation/setup scripts (cacheable stages)"""
        pass
    
    @abstractmethod
    def post_work_scripts(self) -> List[ScriptReference]:
        """Return readiness wait scripts (cacheable stages)"""
        pass
    
    @abstractmethod
    def validation_scripts(self) -> List[ScriptReference]:
        """Return verification scripts (always-run stages, cache_key: null)"""
        pass
    
    @abstractmethod
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate manifests, configs, and stage definitions (async for I/O operations)
        
        Args:
            ctx: Immutable snapshot of platform context (read-only)
        
        Returns:
            AdapterOutput with manifests, stages, and capability data
        """
        pass
    
    def get_embedded_script(self, script_name: str) -> str:
        """Retrieve embedded script content by name"""
        script_path = Path(__file__).parent / "scripts" / script_name
        return script_path.read_text()
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata"""
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())
```

### 3.3 Talos Adapter Implementation

```python
# ztc/adapters/talos/adapter.py
from ztc.adapters.base import PlatformAdapter, InputPrompt, ScriptReference, PipelineStage, AdapterOutput
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from pydantic import BaseModel, Field, validator
from typing import List, Literal

class NodeConfig(BaseModel):
    name: str = Field(..., regex=r"^[a-z0-9-]+$")
    ip: str = Field(..., regex=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    role: Literal["controlplane", "worker"]

class TalosConfig(BaseModel):
    version: str
    factory_image_id: str = Field(..., min_length=64, max_length=64)
    cluster_name: str = Field(..., regex=r"^[a-z0-9-]+$")
    cluster_endpoint: str = Field(..., regex=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$")
    nodes: List[NodeConfig]
    disk_device: str = "/dev/sda"

# Script enums for static validation
class TalosScripts(str, Enum):
    """Talos adapter script resources (validated at class load time)"""
    EMBED_NETWORK = "02-embed-network-manifests.sh"
    INSTALL = "03-install-talos.sh"
    BOOTSTRAP = "04-bootstrap-talos.sh"
    ADD_WORKERS = "05-add-worker-nodes.sh"
    VALIDATE_CLUSTER = "validate-cluster.sh"

class TalosAdapter(PlatformAdapter):
    @property
    def config_model(self):
        return TalosConfig
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Define interactive prompts for Talos configuration"""
        return [
            self.get_version_prompt(),
            InputPrompt(
                name="factory_image_id",
                prompt="Talos factory image ID",
                type="string",
                default="376567988ad370138ad8b2698212367b8edcb69b5fd68c80be1f2ec7d603b4ba",
                help_text="Custom Talos image with embedded extensions"
            ),
            InputPrompt(
                name="cluster_name",
                prompt="Cluster name",
                type="string",
                validation=r"^[a-z0-9-]+$",
                help_text="Alphanumeric + hyphens only"
            ),
            InputPrompt(
                name="cluster_endpoint",
                prompt="Cluster API endpoint",
                type="string",
                validation=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$",
                help_text="Format: IP:PORT (e.g., 46.62.218.181:6443)"
            ),
            InputPrompt(
                name="nodes",
                prompt="Node definitions (JSON array)",
                type="json",
                help_text='[{"name": "cp01", "ip": "46.62.218.181", "role": "controlplane"}]'
            )
        ]
    
    def pre_work_scripts(self) -> List[ScriptReference]:
        """Installation scripts with static validation"""
        return [
            ScriptReference(
                package="ztc.adapters.talos.scripts",
                resource=TalosScripts.EMBED_NETWORK,
                description="Embed Gateway API CRDs and Cilium CNI in Talos config",
                timeout=60
            ),
            ScriptReference(
                package="ztc.adapters.talos.scripts",
                resource=TalosScripts.INSTALL,
                description="Install Talos OS on bare-metal server",
                timeout=600,
                context_data={
                    "server_ip": "$SERVER_IP",
                    "user": "root",
                    "password": "$ROOT_PASSWORD",
                    "confirm_destructive": True
                }
            ),
            ScriptReference(
                package="ztc.adapters.talos.scripts",
                resource=TalosScripts.BOOTSTRAP,
                description="Bootstrap Talos cluster and generate credentials",
                timeout=300,
                context_data={
                    "server_ip": "$SERVER_IP",
                    "environment": "$ENV"
                }
            ),
            ScriptReference(
                package="ztc.adapters.talos.scripts",
                resource=TalosScripts.ADD_WORKERS,
                description="Add worker nodes to cluster",
                timeout=900,
                context_data={
                    "worker_nodes": "$WORKER_NODES",
                    "worker_password": "$WORKER_PASSWORD"
                }
            )
        ]
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """Readiness wait scripts"""
        return []  # Talos doesn't wait for itself
    
    def validation_scripts(self) -> List[ScriptReference]:
        """Verification scripts with static validation"""
        return [
            ScriptReference(
                package="ztc.adapters.talos.scripts",
                resource=TalosScripts.VALIDATE_CLUSTER,
                description="Verify nodes joined cluster",
                timeout=60
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate Talos machine configs and pipeline stages"""
        version = self.config["version"]  # Required field, no fallback
        
        # Use cached Jinja2 environment (no re-initialization)
        manifests = {}
        
        # Get CNI manifests from capability (enum-based, type-safe)
        from ztc.interfaces.capabilities import Capability
        cni_artifacts: CNIArtifacts = ctx.get_capability_data(Capability.CNI)
        cilium_manifests = cni_artifacts.manifests  # Type-safe access
        
        # Render machine configs for each node
        for node in self.config["nodes"]:
            if node["role"] == "controlplane":
                # Use namespaced template access: "adapter_name/template.j2"
                template = self.jinja_env.get_template("talos/controlplane.yaml.j2")
            else:
                template = self.jinja_env.get_template("talos/worker.yaml.j2")
            
            config_content = template.render(
                cluster_name=self.config["cluster_name"],
                cluster_endpoint=self.config["cluster_endpoint"],
                node=node,
                factory_image_id=self.config["factory_image_id"],
                cilium_manifests=cilium_manifests,
                talos_version=version
            )
            
            manifests[f"nodes/{node['name']}/config.yaml"] = config_content
        
        # Render talosconfig
        talosconfig_template = self.jinja_env.get_template("talos/talosconfig.j2")
        manifests["talosconfig"] = talosconfig_template.render(
            cluster_name=self.config["cluster_name"],
            cluster_endpoint=self.config["cluster_endpoint"]
        )
        
        # Generate pipeline stages from lifecycle hooks
        stages = self._generate_stages()
        
        return AdapterOutput(
            manifests=manifests,
            stages=stages,
            env_vars={"TALOS_VERSION": version},
            capabilities={
                "kubernetes-api": KubernetesAPICapability(
                    cluster_endpoint=self.config["cluster_endpoint"],
                    kubeconfig_path="~/.kube/config",
                    version=">=1.28"
                )
            },
            data={  # Legacy support
                "cluster_endpoint": self.config["cluster_endpoint"],
                "kubeconfig_path": "~/.kube/config",
                "cni_embedded": True,
                "nodes": self.config["nodes"]
            }
        )
    
    def _generate_stages(self) -> List[PipelineStage]:
        """Generate pipeline stages from lifecycle hooks"""
        stages = []
        
        # Pre-work stages (install)
        for script_ref in self.pre_work_scripts():
            stages.append(PipelineStage(
                name=script_ref.uri.split("://")[1].replace(".sh", "").replace("-", "_"),
                description=script_ref.description,
                script=script_ref.uri,
                cache_key=script_ref.uri.split("://")[1].replace(".sh", "").replace("-", "_"),
                required=True,
                args=script_ref.args,
                phase=self.phase,
                barrier="cluster_installed" if "install" in script_ref.uri else "local"
            ))
        
        # Post-work stages (wait) - none for Talos
        
        # Validation stages (always run)
        for script_ref in self.validation_scripts():
            stages.append(PipelineStage(
                name=script_ref.uri.split("://")[1].replace(".sh", "").replace("-", "_"),
                description=script_ref.description,
                script=script_ref.uri,
                cache_key=None,  # Always run
                required=True,
                phase=self.phase,
                barrier="cluster_accessible"
            ))
        
        return stages
```

### 3.4 Cilium Adapter Implementation

```python
# ztc/adapters/cilium/adapter.py
from pydantic import BaseModel, Field
from typing import Optional

class CiliumConfig(BaseModel):
    version: str
    bgp_enabled: bool = False
    bgp_asn: Optional[int] = Field(None, ge=1, le=4294967295)

class CiliumAdapter(PlatformAdapter):
    @property
    def config_model(self):
        return CiliumConfig
    
    def validate_upstream_context(self, current_config: Dict, full_platform_context: Dict) -> bool:
        """Validate Cilium config against OS selection (deprecated, use get_invalid_fields)"""
        selected_os = full_platform_context.get("os")
        if selected_os != "talos":
            return False
        return True
    
    def get_invalid_fields(self, current_config: Dict, full_platform_context: Dict) -> List[str]:
        """Return invalid fields when OS changes (differential validation)
        
        Cilium embedding in Talos is OS-specific. If OS changes from Talos to Ubuntu,
        only the embedding-related fields become invalid, not the entire config.
        """
        invalid = []
        selected_os = full_platform_context.get("os")
        
        # If OS is not Talos, embedding-related config is invalid
        if selected_os != "talos":
            # Only invalidate Talos-specific fields, keep version/BGP config
            if "embedded_mode" in current_config:
                invalid.append("embedded_mode")
        
        return invalid
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Define interactive prompts for Cilium configuration"""
        return [
            self.get_version_prompt(),
            InputPrompt(
                name="bgp_enabled",
                prompt="Enable BGP mode?",
                type="boolean",
                default=False,
                help_text="BGP mode for bare-metal load balancing"
            ),
            InputPrompt(
                name="bgp_asn",
                prompt="BGP ASN",
                type="integer",
                default=64512,
                help_text="Required if BGP enabled"
            )
        ]
    
    def pre_work_scripts(self) -> List[ScriptReference]:
        """Installation scripts"""
        return []  # Cilium embedded in Talos config, no separate install
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """Readiness wait scripts"""
        return [
            ScriptReference(
                uri="cilium://wait-cilium.sh",
                description="Wait for Cilium CNI to be ready",
                timeout=300
            ),
            ScriptReference(
                uri="cilium://wait-gateway-api.sh",
                description="Validate Gateway API CRDs readiness",
                timeout=120
            )
        ]
    
    def validation_scripts(self) -> List[ScriptReference]:
        """Verification scripts"""
        return [
            ScriptReference(
                uri="cilium://validate-cni.sh",
                description="Verify pod networking",
                timeout=60
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate Cilium manifests"""
        version = self.config["version"]  # Required field, no fallback
        
        # Use cached Jinja2 environment with namespaced access
        template = self.jinja_env.get_template("cilium/manifests.yaml.j2")
        
        manifests_content = template.render(
            version=version,
            bgp_enabled=self.config["bgp_enabled"],
            bgp_asn=self.config["bgp_asn"]
        )
        
        stages = self._generate_stages()
        
        return AdapterOutput(
            manifests={"manifests.yaml": manifests_content},
            stages=stages,
            env_vars={"CILIUM_VERSION": version},
            capabilities={
                "cni": CNIArtifacts(
                    manifests=manifests_content,
                    cni_conf=None,
                    ready=False
                ),
                "gateway-api": GatewayAPICapability(
                    version="v1",
                    crds_embedded=True
                )
            },
            data={  # Legacy support
                "cni_ready": False,
                "gateway_api_version": "v1",
                "bgp_enabled": self.config["bgp_enabled"],
                "manifests": manifests_content
            }
        )
```

### 3.5 Hetzner Adapter Implementation

```python
# ztc/adapters/hetzner/adapter.py
from pydantic import BaseModel, Field, validator

class HetznerConfig(BaseModel):
    api_token: str = Field(..., min_length=64, max_length=64)
    server_ips: str = Field(..., regex=r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(,\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})*$")
    rescue_mode_confirm: str = Field(..., regex=r"^DESTROY$")
    
    @validator('server_ips')
    def validate_ips(cls, v):
        ips = v.split(',')
        for ip in ips:
            octets = ip.split('.')
            if not all(0 <= int(octet) <= 255 for octet in octets):
                raise ValueError(f"Invalid IP address: {ip}")
        return v

class HetznerAdapter(PlatformAdapter):
    @property
    def config_model(self):
        return HetznerConfig
    
    def get_required_inputs(self) -> List[InputPrompt]:
        """Define interactive prompts for Hetzner configuration"""
        return [
            InputPrompt(
                name="api_token",
                prompt="Hetzner API token",
                type="password",
                help_text="Get from https://console.hetzner.cloud/projects"
            ),
            InputPrompt(
                name="server_ips",
                prompt="Server IPs (comma-separated)",
                type="string",
                validation=r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(,\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})*$",
                help_text="Example: 46.62.218.181,95.216.151.243"
            ),
            InputPrompt(
                name="rescue_mode_confirm",
                prompt="⚠️  WARNING: This will WIPE ALL DATA on the servers. Type 'DESTROY' to confirm",
                type="string",
                validation=r"^DESTROY$",
                help_text="Required for Talos installation - this is a DESTRUCTIVE operation"
            )
        ]
    
    def pre_work_scripts(self) -> List[ScriptReference]:
        """Installation scripts"""
        return [
            ScriptReference(
                uri="hetzner://enable-rescue-mode.sh",
                description="Enable rescue mode for all servers",
                timeout=300
            )
        ]
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """Readiness wait scripts"""
        return []  # Hetzner is infrastructure, no readiness wait
    
    def validation_scripts(self) -> List[ScriptReference]:
        """Verification scripts"""
        return [
            ScriptReference(
                uri="hetzner://validate-server-ids.sh",
                description="Verify providerID injection",
                timeout=60
            )
        ]
    
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate Hetzner configuration (no manifests, only data export)"""
        server_ips = self.config["server_ips"].split(",")
        
        # Query Hetzner API for server IDs (async I/O)
        server_ids = {}
        for ip in server_ips:
            server_id = await self._get_server_id_by_ip(ip)
            server_ids[ip] = server_id
        
        stages = self._generate_stages()
        
        return AdapterOutput(
            manifests={},  # No manifests for Hetzner
            stages=stages,
            env_vars={"HCLOUD_TOKEN": self.config["api_token"]},
            capabilities={
                "cloud-infrastructure": CloudInfrastructureCapability(
                    provider="hetzner",
                    server_ids=server_ids,
                    rescue_mode_enabled=True
                )
            },
            data={  # Legacy support
                "server_ids": server_ids,
                "rescue_mode_enabled": True
            }
        )
    
    async def _get_server_id_by_ip(self, ip: str) -> str:
        """Query Hetzner API for server ID by IP (async)"""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.config['api_token']}"}
            async with session.get("https://api.hetzner.cloud/v1/servers", headers=headers) as resp:
                data = await resp.json()
                for server in data["servers"]:
                    if server["public_net"]["ipv4"]["ip"] == ip:
                        return str(server["id"])
                raise ValueError(f"Server with IP {ip} not found")
```

## 4. Engine Architecture

### 4.1 Core Engine with Shared Jinja Environment

```python
# ztc/engine.py
from pathlib import Path
from typing import List, Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader
import shutil
import hashlib
import yaml

class PlatformEngine:
    def __init__(self, platform_yaml: Path, debug: bool = False):
        self.platform = self.load_platform(platform_yaml)
        self.adapter_registry = AdapterRegistry()
        self.context = PlatformContext()
        self.debug_mode = debug
        
        # Shared Jinja2 environment for all adapters (performance optimization)
        self.jinja_env = self._create_shared_jinja_env()
    
    def _create_shared_jinja_env(self) -> Environment:
        """Create shared Jinja2 environment with namespaced adapter templates
        
        Performance: Single environment with unified loader cache instead of 19 separate
        environments. Reduces memory footprint and filesystem stat() calls.
        
        Safety: PrefixLoader prevents namespace collisions. Templates accessed via
        "adapter_name/template.j2" syntax, ensuring correct template resolution.
        """
        from jinja2 import PrefixLoader, PackageLoader
        
        prefix_mapping = {}
        
        # Build prefix mapping: "talos" -> PackageLoader("ztc.adapters.talos", "templates")
        for adapter_name in self.adapter_registry.list_adapters():
            adapter_class = self.adapter_registry.get_adapter_class(adapter_name)
            # Use PackageLoader for robust binary packaging
            prefix_mapping[adapter_name] = PackageLoader(
                f"ztc.adapters.{adapter_name}",
                "templates"
            )
        
        # Create unified loader with namespace prefixes
        return Environment(
            loader=PrefixLoader(prefix_mapping),
            auto_reload=False,  # Production optimization
            enable_async=True   # Support async rendering
        )
    
    async def render(self, partial: Optional[List[str]] = None) -> RenderResult:
        """Main render pipeline (async for I/O-bound adapters)"""
        # 1. Validate platform.yaml
        self.validate_platform()
        
        # 2. Check if render needed
        if not self.needs_render():
            return RenderResult.NO_CHANGES
        
        # 3. Resolve adapter dependencies and inject shared Jinja environment
        adapters = self.resolve_adapters(partial)
        
        # Inject shared Jinja environment into all adapters
        for adapter in adapters:
            adapter._jinja_env = self.jinja_env
        
        # 4. Use fixed workspace
        workspace = Path(".zerotouch-cache/workspace")
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)
        
        generated_dir = workspace / "generated"
        generated_dir.mkdir(parents=True)
        
        try:
            # 5. Render adapters with immutable context snapshots
            # Adapters receive read-only snapshots, engine updates mutable context
            for adapter in adapters:
                snapshot = self.context.snapshot()  # Immutable snapshot
                output = await adapter.render(snapshot)  # Pure function
                
                # Engine updates context (not adapter)
                self.write_adapter_output(generated_dir, adapter.name, output)
                self.context.register_output(adapter.name, output)
            
            # 6. Generate pipeline YAML from adapter stages
            self.generate_pipeline_yaml(adapters, workspace)
            
            # 7. Write debug scripts for observability (IaC principle)
            self.write_debug_scripts(adapters, generated_dir)
            
            # 8. Validate generated artifacts
            self.validate_artifacts(generated_dir)
            
            # 9. Atomic swap
            self.atomic_swap_generated(workspace)
            
            # 10. Generate lock file
            artifacts_hash = self.hash_directory(Path("platform/generated"))
            self.generate_lock_file(artifacts_hash, adapters)
            
            # 11. Clean up workspace
            if workspace.exists():
                shutil.rmtree(workspace)
            
            return RenderResult.SUCCESS
        
        except Exception as e:
            if self.debug_mode:
                print(f"❌ Render failed. Artifacts preserved at: {workspace}")
            else:
                if workspace.exists():
                    shutil.rmtree(workspace)
            raise RenderError(f"Render failed: {e}")
    
    def resolve_adapters(self, partial: Optional[List[str]] = None) -> List[PlatformAdapter]:
        """Resolve adapter dependencies via phase + capability matching"""
        # 1. Load adapters from platform.yaml (required field)
        adapter_configs = self.platform["adapters"]
        adapters = []
        
        for adapter_name, adapter_config in adapter_configs.items():
            adapter_class = self.adapter_registry.get(adapter_config["type"])
            adapters.append(adapter_class(adapter_config))
        
        # 2. Build capability registry
        capability_registry = self._build_capability_registry(adapters)
        
        # 3. Resolve capability requirements to concrete adapters
        resolved_adapters = self._resolve_capabilities(adapters, capability_registry)
        
        # 4. Group by phase
        phases = {"foundation": [], "networking": [], "platform": [], "services": []}
        for adapter in resolved_adapters:
            phases[adapter.phase].append(adapter)
        
        # 5. Topological sort within each phase
        ordered = []
        for phase in ["foundation", "networking", "platform", "services"]:
            phase_adapters = self._topological_sort(phases[phase])
            ordered.extend(phase_adapters)
        
        return ordered
    
    def generate_pipeline_yaml(self, adapters: List[PlatformAdapter], workspace: Path):
        """Generate production.yaml from adapter stage definitions"""
        pipeline = {
            "mode": "production",
            "total_steps": 0,
            "stages": []
        }
        
        # Collect stages from all adapters
        for adapter in adapters:
            output = self.context.get_output(adapter.name)
            pipeline["stages"].extend(self._convert_stages_to_yaml(output.stages))
        
        pipeline["total_steps"] = len(pipeline["stages"])
        
        # Write pipeline YAML
        pipeline_path = workspace / "production.yaml"
        with open(pipeline_path, "w") as f:
            yaml.dump(pipeline, f, sort_keys=False)
    
    def write_debug_scripts(self, adapters: List[PlatformAdapter], generated_dir: Path):
        """Write scripts to debug directory for observability (break-glass principle)
        
        Enables operators to inspect and manually execute bootstrap logic when
        CLI fails. Aligns with Infrastructure as Code principles.
        """
        debug_dir = generated_dir / "debug" / "scripts"
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        for adapter in adapters:
            output = self.context.get_output(adapter.name)
            adapter_debug_dir = debug_dir / adapter.name
            adapter_debug_dir.mkdir(exist_ok=True)
            
            # Extract and write all scripts referenced by this adapter
            for stage in output.stages:
                script_ref = self._find_script_reference(adapter, stage)
                if script_ref:
                    script_content = adapter.get_embedded_script(script_ref.resource.value)
                    script_path = adapter_debug_dir / script_ref.resource.value
                    script_path.write_text(script_content)
                    script_path.chmod(0o755)
                    
                    # Write context data if present
                    if script_ref.context_data:
                        context_path = adapter_debug_dir / f"{script_ref.resource.value}.context.json"
                        context_path.write_text(json.dumps(script_ref.context_data, indent=2))
        
        # Write README for operators
        readme_path = debug_dir / "README.md"
        readme_path.write_text("""# Debug Scripts

These scripts are extracted from the ZTC binary for debugging purposes.

## Usage

1. Review scripts in adapter-specific directories
2. Modify as needed for debugging
3. Execute manually or via `stage-executor.sh`

## Context Files

Scripts with `.context.json` files read data via `$ZTC_CONTEXT_FILE` environment variable.

Example:
```bash
export ZTC_CONTEXT_FILE=talos/03-install-talos.sh.context.json
bash talos/03-install-talos.sh
```

## Warning

These scripts are for debugging only. Production bootstraps should use `ztc bootstrap`.
""")
    
    def _find_script_reference(self, adapter: PlatformAdapter, stage: PipelineStage) -> Optional[ScriptReference]:
        """Find ScriptReference for a given stage"""
        # Check pre_work, post_work, and validation scripts
        all_scripts = (
            adapter.pre_work_scripts() +
            adapter.post_work_scripts() +
            adapter.validation_scripts()
        )
        
        for script_ref in all_scripts:
            if script_ref.uri == stage.script:
                return script_ref
        
        return None
    
    def _convert_stages_to_yaml(self, stages: List[PipelineStage]) -> List[Dict]:
        """Convert PipelineStage objects to YAML-compatible dicts"""
        yaml_stages = []
        
        for stage in stages:
            yaml_stage = {
                "name": stage.name,
                "description": stage.description,
                "script": stage.script,
                "cache_key": stage.cache_key,
                "required": stage.required
            }
            
            if stage.args:
                yaml_stage["args"] = stage.args
            
            if stage.skip_if_empty:
                yaml_stage["skip_if_empty"] = stage.skip_if_empty
            
            yaml_stages.append(yaml_stage)
        
        return yaml_stages
```

### 4.2 Dependency Resolution Algorithm

```python
# ztc/engine/resolver.py
class DependencyResolver:
    def resolve(self, adapters: List[PlatformAdapter]) -> List[PlatformAdapter]:
        """Topological sort with phase-based ordering"""
        # Build capability registry
        capability_registry = {}
        for adapter in adapters:
            metadata = adapter.load_metadata()
            # Raises KeyError if 'provides' missing - adapters must declare capabilities
            for capability in metadata["provides"]:
                cap_name = capability["capability"] if isinstance(capability, dict) else capability
                capability_registry[cap_name] = adapter
        
        # Build dependency graph
        graph = {}
        in_degree = {}
        
        for adapter in adapters:
            graph[adapter] = []
            in_degree[adapter] = 0
        
        for adapter in adapters:
            metadata = adapter.load_metadata()
            # Raises KeyError if 'requires' missing - adapters must declare dependencies
            for requirement in metadata["requires"]:
                req_cap = requirement["capability"] if isinstance(requirement, dict) else requirement
                
                if req_cap not in capability_registry:
                    raise MissingCapabilityError(
                        f"Adapter '{adapter.name}' requires capability '{req_cap}' "
                        f"but no adapter provides it"
                    )
                
                provider = capability_registry[req_cap]
                graph[provider].append(adapter)
                in_degree[adapter] += 1
        
        # Kahn's algorithm for topological sort
        queue = [adapter for adapter in adapters if in_degree[adapter] == 0]
        result = []
        
        while queue:
            adapter = queue.pop(0)
            result.append(adapter)
            
            for dependent in graph[adapter]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        if len(result) != len(adapters):
            raise CircularDependencyError("Circular dependency detected in adapters")
        
        return result
```

### 4.3 Platform Context with Immutable Snapshots

```python
# ztc/engine/context.py
from typing import Protocol, TypedDict, Any, Dict, Type
from pydantic import BaseModel
from ztc.interfaces.capabilities import CAPABILITY_CONTRACTS, Capability

class ContextSnapshot:
    """Immutable snapshot of platform context (read-only for adapters)"""
    def __init__(self, capabilities: Dict[Capability, BaseModel], outputs: Dict[str, 'AdapterOutput']):
        self._capabilities = capabilities.copy()  # Shallow copy for immutability
        self._outputs = outputs.copy()
        self.environment = "production"
    
    def get_capability_data(self, capability: Capability) -> BaseModel:
        """Get strongly-typed capability data using enum (type-safe)
        
        Args:
            capability: Capability enum (e.g., Capability.CNI)
        
        Returns:
            Validated capability data as Pydantic model
        
        Raises:
            CapabilityNotFoundError: If capability not available
            TypeError: If capability data doesn't match expected type
        """
        if capability not in self._capabilities:
            raise CapabilityNotFoundError(
                f"No adapter provides capability '{capability.value}'"
            )
        
        capability_data = self._capabilities[capability]
        expected_type = CAPABILITY_CONTRACTS[capability]
        
        # Type safety check
        if not isinstance(capability_data, expected_type):
            raise TypeError(
                f"Capability '{capability.value}' expected type {expected_type.__name__}, "
                f"got {type(capability_data).__name__}"
            )
        
        return capability_data
    
    def has_capability(self, capability: Capability) -> bool:
        """Check if capability is available"""
        return capability in self._capabilities
    
    # Legacy methods (deprecated)
    def get_output(self, adapter_name: str) -> 'AdapterOutput':
        """Get complete output from upstream adapter (legacy, use get_capability_data)"""
        if adapter_name not in self._outputs:
            raise AdapterNotExecutedError(
                f"Adapter '{adapter_name}' has not been executed yet"
            )
        return self._outputs[adapter_name]

class PlatformContext:
    """Mutable context managed by Engine (not exposed to adapters)"""
    def __init__(self):
        self._outputs = {}
        self._capabilities: Dict[Capability, BaseModel] = {}  # Enum-keyed registry
        self.environment = "production"
    
    def register_output(self, adapter_name: str, output: 'AdapterOutput'):
        """Register adapter output and validate capability contracts"""
        self._outputs[adapter_name] = output
        
        # Register and validate capabilities
        for capability_str, capability_data in output.capabilities.items():
            # Convert string to enum
            try:
                capability = Capability(capability_str)
            except ValueError:
                raise ValueError(
                    f"Adapter '{adapter_name}' provides unknown capability '{capability_str}'. "
                    f"Valid capabilities: {[c.value for c in Capability]}"
                )
            
            # Enforce Pydantic model requirement
            if not isinstance(capability_data, BaseModel):
                raise TypeError(
                    f"Adapter '{adapter_name}' capability '{capability.value}' must be a Pydantic model, "
                    f"got {type(capability_data).__name__}"
                )
            
            # Validate against registered contract
            expected_type = CAPABILITY_CONTRACTS[capability]
            if not isinstance(capability_data, expected_type):
                raise TypeError(
                    f"Adapter '{adapter_name}' capability '{capability.value}' must be {expected_type.__name__}, "
                    f"got {type(capability_data).__name__}"
                )
            
            # Check for conflicts
            if capability in self._capabilities:
                raise CapabilityConflictError(
                    f"Capability '{capability.value}' already provided by another adapter"
                )
            
            self._capabilities[capability] = capability_data
    
    def snapshot(self) -> ContextSnapshot:
        """Create immutable snapshot for adapter consumption"""
        return ContextSnapshot(
            capabilities=self._capabilities,
            outputs=self._outputs
        )
    
    def has_capability(self, capability: Capability) -> bool:
        """Check if capability is available"""
        return capability in self._capabilities
```

## 5. Bootstrap Execution

### 5.0 Eject Workflow (Break-Glass Mode)

```python
# ztc/workflows/eject.py
from pathlib import Path
from rich.console import Console
from rich.progress import Progress
import yaml
import json
from datetime import datetime

class EjectWorkflow:
    """Eject workflow for manual debugging and intervention
    
    Extracts all embedded scripts, context files, and pipeline to a debug directory.
    Operators can then inspect, modify, and manually execute bootstrap logic.
    """
    
    def __init__(self, console: Console, output_dir: Path, env: str):
        self.console = console
        self.output_dir = Path(output_dir)
        self.env = env
        self.engine = None
    
    def run(self):
        """Execute eject workflow"""
        self.console.print(f"[bold blue]Ejecting bootstrap artifacts to {self.output_dir}[/bold blue]")
        
        # 1. Validate prerequisites
        self.validate_prerequisites()
        
        # 2. Load platform.yaml and initialize engine
        platform_yaml = Path("platform.yaml")
        self.engine = PlatformEngine(platform_yaml)
        
        # 3. Resolve adapters
        adapters = self.engine.resolve_adapters()
        
        # 4. Create output directory structure
        self.create_directory_structure()
        
        # 5. Extract scripts with context files
        with Progress() as progress:
            task = progress.add_task("[cyan]Extracting scripts...", total=len(adapters))
            
            for adapter in adapters:
                self.extract_adapter_scripts(adapter)
                progress.update(task, advance=1)
        
        # 6. Copy pipeline.yaml
        self.copy_pipeline_yaml()
        
        # 7. Generate execution guide
        self.generate_execution_guide(adapters)
        
        # 8. Display summary
        self.display_summary()
    
    def validate_prerequisites(self):
        """Validate that platform.yaml and generated artifacts exist"""
        if not Path("platform.yaml").exists():
            raise FileNotFoundError(
                "platform.yaml not found. Run 'ztc init' first."
            )
        
        if not Path("platform/generated").exists():
            raise FileNotFoundError(
                "Generated artifacts not found. Run 'ztc render' first."
            )
    
    def create_directory_structure(self):
        """Create output directory structure"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "scripts").mkdir(exist_ok=True)
        (self.output_dir / "context").mkdir(exist_ok=True)
        (self.output_dir / "pipeline").mkdir(exist_ok=True)
    
    def extract_adapter_scripts(self, adapter: PlatformAdapter):
        """Extract all scripts for an adapter with context files"""
        adapter_scripts_dir = self.output_dir / "scripts" / adapter.name
        adapter_context_dir = self.output_dir / "context" / adapter.name
        
        adapter_scripts_dir.mkdir(parents=True, exist_ok=True)
        adapter_context_dir.mkdir(parents=True, exist_ok=True)
        
        # Get all script references from adapter lifecycle hooks
        all_scripts = (
            adapter.pre_work_scripts() +
            adapter.post_work_scripts() +
            adapter.validation_scripts()
        )
        
        for script_ref in all_scripts:
            # Extract script content
            script_content = adapter.get_embedded_script(script_ref.resource.value)
            script_path = adapter_scripts_dir / script_ref.resource.value
            script_path.write_text(script_content)
            script_path.chmod(0o755)
            
            # Write context file if present
            if script_ref.context_data:
                context_file = adapter_context_dir / f"{script_ref.resource.value}.context.json"
                context_file.write_text(json.dumps(script_ref.context_data, indent=2))
    
    def copy_pipeline_yaml(self):
        """Copy pipeline.yaml to output directory"""
        pipeline_src = Path(f"bootstrap/pipeline/{self.env}.yaml")
        
        if not pipeline_src.exists():
            self.console.print(
                f"[yellow]⚠[/yellow] Pipeline file not found: {pipeline_src}"
            )
            return
        
        pipeline_dst = self.output_dir / "pipeline" / f"{self.env}.yaml"
        pipeline_dst.write_text(pipeline_src.read_text())
    
    def generate_execution_guide(self, adapters: List[PlatformAdapter]):
        """Generate README with execution instructions"""
        guide_content = f"""# Ejected Bootstrap Artifacts

**Environment:** {self.env}
**Ejected:** {datetime.now().isoformat()}

## Directory Structure

```
{self.output_dir}/
├── scripts/              # Extracted scripts by adapter
│   ├── hetzner/
│   ├── cilium/
│   └── talos/
├── context/              # Context files for scripts
│   ├── hetzner/
│   ├── cilium/
│   └── talos/
├── pipeline/             # Pipeline YAML
│   └── {self.env}.yaml
└── README.md             # This file
```

## Adapters

"""
        
        for adapter in adapters:
            guide_content += f"\n### {adapter.name}\n\n"
            guide_content += f"**Phase:** {adapter.phase}\n\n"
            guide_content += "**Scripts:**\n\n"
            
            all_scripts = (
                adapter.pre_work_scripts() +
                adapter.post_work_scripts() +
                adapter.validation_scripts()
            )
            
            for script_ref in all_scripts:
                guide_content += f"- `{script_ref.resource.value}` - {script_ref.description}\n"
                
                if script_ref.context_data:
                    guide_content += f"  - Context: `context/{adapter.name}/{script_ref.resource.value}.context.json`\n"
            
            guide_content += "\n"
        
        guide_content += """
## Manual Execution

### Using Context Files

Scripts that have context files read data via the `$ZTC_CONTEXT_FILE` environment variable:

```bash
export ZTC_CONTEXT_FILE="context/talos/03-install-talos.sh.context.json"
bash scripts/talos/03-install-talos.sh
```

### Reading Context in Scripts

Example bash script reading context.json:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Read context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

# Parse JSON with jq
SERVER_IP=$(jq -r '.server_ip' "$ZTC_CONTEXT_FILE")
CLUSTER_NAME=$(jq -r '.cluster_name' "$ZTC_CONTEXT_FILE")

echo "Installing Talos on $SERVER_IP for cluster $CLUSTER_NAME"
```

### Using stage-executor.sh

You can use the existing stage-executor.sh with ejected artifacts:

```bash
# Copy stage-executor.sh to output directory
cp /path/to/stage-executor.sh {self.output_dir}/

# Execute pipeline
cd {self.output_dir}
./stage-executor.sh pipeline/{self.env}.yaml
```

### Manual Stage Execution

Execute stages individually for debugging:

```bash
# Stage 1: Enable rescue mode
export HCLOUD_TOKEN="your-token"
bash scripts/hetzner/enable-rescue-mode.sh

# Stage 2: Install Talos
export ZTC_CONTEXT_FILE="context/talos/03-install-talos.sh.context.json"
bash scripts/talos/03-install-talos.sh
```

## Modifying Scripts

You can modify ejected scripts for debugging or edge cases:

1. Edit script in `scripts/<adapter>/<script-name>.sh`
2. Update context file in `context/<adapter>/<script-name>.sh.context.json` if needed
3. Execute manually or via stage-executor.sh

## Re-integrating Changes

If you fix issues in ejected scripts:

1. Update the adapter's embedded script in the ZTC source code
2. Rebuild the ZTC binary
3. Run `ztc render` to regenerate artifacts
4. Run `ztc bootstrap` to execute with fixed scripts

## Warning

Ejected artifacts are for debugging only. Production bootstraps should use `ztc bootstrap`.
"""
        
        readme_path = self.output_dir / "README.md"
        readme_path.write_text(guide_content)
    
    def display_summary(self):
        """Display eject summary"""
        from rich.table import Table
        
        table = Table(title="Eject Summary")
        table.add_column("Component", style="cyan")
        table.add_column("Location", style="yellow")
        
        table.add_row("Scripts", f"{self.output_dir}/scripts/")
        table.add_row("Context Files", f"{self.output_dir}/context/")
        table.add_row("Pipeline", f"{self.output_dir}/pipeline/{self.env}.yaml")
        table.add_row("Execution Guide", f"{self.output_dir}/README.md")
        
        self.console.print(table)
        self.console.print(
            f"\n[green]✓[/green] Bootstrap artifacts ejected to [bold]{self.output_dir}[/bold]"
        )
        self.console.print(
            f"\n[dim]Read {self.output_dir}/README.md for execution instructions[/dim]"
        )
```

### 5.1 Signal-Safe Temporary Directory

```python
# ztc/utils/context_managers.py
import signal
import shutil
import atexit
import tempfile
from pathlib import Path
from typing import Optional

class SecureTempDir:
    """Signal-safe temporary directory with guaranteed cleanup
    
    Ensures cleanup on SIGINT/SIGTERM in addition to normal exit.
    Critical for security: prevents sensitive scripts from lingering in /tmp.
    """
    
    def __init__(self, prefix: str = "ztc-secure-"):
        self.prefix = prefix
        self.path: Optional[Path] = None
        self._cleanup_registered = False
        self._original_sigint_handler = None
        self._original_sigterm_handler = None
    
    def __enter__(self) -> Path:
        """Create secure temp directory with 0700 permissions"""
        self.path = Path(tempfile.mkdtemp(prefix=self.prefix))
        
        # Register cleanup with atexit (normal exit)
        if not self._cleanup_registered:
            atexit.register(self._cleanup)
            self._cleanup_registered = True
        
        # Register signal handlers (forced termination)
        self._original_sigint_handler = signal.signal(signal.SIGINT, self._signal_handler)
        self._original_sigterm_handler = signal.signal(signal.SIGTERM, self._signal_handler)
        
        return self.path
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup on normal context exit"""
        self._cleanup()
        self._restore_signal_handlers()
        return False
    
    def _cleanup(self):
        """Remove temporary directory (idempotent)"""
        if self.path and self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)
            self.path = None
    
    def _signal_handler(self, signum, frame):
        """Handle SIGINT/SIGTERM by cleaning up and re-raising"""
        self._cleanup()
        self._restore_signal_handlers()
        
        # Re-raise signal to allow normal signal handling
        if signum == signal.SIGINT:
            raise KeyboardInterrupt
        elif signum == signal.SIGTERM:
            raise SystemExit(128 + signum)
    
    def _restore_signal_handlers(self):
        """Restore original signal handlers"""
        if self._original_sigint_handler:
            signal.signal(signal.SIGINT, self._original_sigint_handler)
        if self._original_sigterm_handler:
            signal.signal(signal.SIGTERM, self._original_sigterm_handler)
```

### 5.1.1 Vacuum Command (Stale Temp Cleanup)

```python
# ztc/utils/vacuum.py
import tempfile
import time
from pathlib import Path
from rich.console import Console
from rich.table import Table

class VacuumCommand:
    """Clean up stale temporary directories from crashed runs
    
    Handles SIGKILL (9) scenarios where SecureTempDir cleanup couldn't run.
    Provides a safety net for sensitive data left in /tmp after hard crashes.
    """
    
    def __init__(self, console: Console, max_age_minutes: int = 60):
        self.console = console
        self.max_age_minutes = max_age_minutes
        self.temp_root = Path(tempfile.gettempdir())
    
    def execute(self):
        """Find and remove stale ztc-secure-* directories"""
        stale_dirs = self.find_stale_directories()
        
        if not stale_dirs:
            self.console.print("[green]✓[/green] No stale temporary directories found")
            return
        
        # Display findings
        table = Table(title="Stale Temporary Directories")
        table.add_column("Directory", style="yellow")
        table.add_column("Age (minutes)", style="cyan")
        table.add_column("Size", style="magenta")
        
        for dir_info in stale_dirs:
            table.add_row(
                dir_info["path"].name,
                str(dir_info["age_minutes"]),
                self.format_size(dir_info["size_bytes"])
            )
        
        self.console.print(table)
        
        # Clean up
        removed_count = 0
        for dir_info in stale_dirs:
            try:
                shutil.rmtree(dir_info["path"], ignore_errors=True)
                removed_count += 1
            except Exception as e:
                self.console.print(
                    f"[yellow]⚠[/yellow] Failed to remove {dir_info['path'].name}: {e}"
                )
        
        self.console.print(
            f"[green]✓[/green] Removed {removed_count}/{len(stale_dirs)} stale directories"
        )
    
    def find_stale_directories(self) -> List[Dict]:
        """Find ztc-secure-* directories older than max_age_minutes"""
        stale_dirs = []
        current_time = time.time()
        cutoff_time = current_time - (self.max_age_minutes * 60)
        
        # Search for ztc-secure-* directories in temp root
        for path in self.temp_root.glob("ztc-secure-*"):
            if not path.is_dir():
                continue
            
            # Check modification time (last activity)
            mtime = path.stat().st_mtime
            
            if mtime < cutoff_time:
                age_minutes = int((current_time - mtime) / 60)
                size_bytes = self.get_directory_size(path)
                
                stale_dirs.append({
                    "path": path,
                    "age_minutes": age_minutes,
                    "size_bytes": size_bytes
                })
        
        return stale_dirs
    
    def get_directory_size(self, path: Path) -> int:
        """Calculate total size of directory in bytes"""
        total_size = 0
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
        except Exception:
            pass  # Ignore permission errors
        return total_size
    
    def format_size(self, size_bytes: int) -> str:
        """Format bytes as human-readable size"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
```

**Automatic Vacuum on CLI Startup:**

```python
# ztc/cli.py
def main():
    """CLI entry point with automatic vacuum"""
    # Run vacuum on startup (silent if no stale dirs)
    try:
        vacuum = VacuumCommand(Console(), max_age_minutes=60)
        vacuum.execute()
    except Exception:
        pass  # Don't block CLI startup on vacuum failures
    
    # Run Typer app
    app()
```

### 5.2 Bootstrap Command Implementation

```python
# ztc/commands/bootstrap.py
import subprocess
import json
from pathlib import Path
from ztc.utils.context_managers import SecureTempDir
import shutil

class BootstrapCommand:
    def __init__(self, env: str, skip_cache: bool = False):
        self.env = env
        self.skip_cache = skip_cache
        self.repo_root = Path.cwd()
    
    def execute(self):
        """Execute bootstrap pipeline via stage-executor.sh with AOT script extraction"""
        # 1. Validate runtime dependencies (ZeroTouch promise)
        self.validate_runtime_dependencies()
        
        # 2. Validate lock file
        self.validate_lock_file()
        
        # 3. Load pipeline YAML
        pipeline_yaml = self.repo_root / "bootstrap" / "pipeline" / "production.yaml"
        pipeline = yaml.safe_load(pipeline_yaml.read_text())
        
        # 4. Extract all scripts ahead-of-time to signal-safe secure temp directory
        with SecureTempDir(prefix="ztc-secure-") as temp_dir:
            script_map = self.extract_all_scripts(pipeline["stages"], temp_dir)
            
            # 5. Generate runtime manifest mapping stage IDs to physical paths
            runtime_manifest = temp_dir / "runtime_manifest.json"
            runtime_manifest.write_text(json.dumps(script_map, indent=2))
            
            # 6. Prepare environment variables
            env_vars = self.prepare_env_vars()
            
            # 7. Execute stage-executor.sh with script map
            stage_executor = self.repo_root / "scripts" / "bootstrap" / "pipeline" / "stage-executor.sh"
            stage_executor.chmod(0o755)
            
            result = subprocess.run(
                [str(stage_executor), str(pipeline_yaml), "--script-map", str(runtime_manifest)],
                env={**os.environ, **env_vars},
                cwd=self.repo_root
            )
            
            if result.returncode != 0:
                raise BootstrapError(f"Bootstrap failed with exit code {result.returncode}")
    
    def validate_runtime_dependencies(self):
        """Validate required runtime dependencies exist (ZeroTouch correctness)
        
        The stage-executor.sh and scripts rely on jq/yq for JSON/YAML parsing.
        Failing fast here prevents mid-bootstrap crashes and upholds the ZeroTouch promise.
        
        Raises:
            RuntimeDependencyError: If required tools are missing or incompatible
        """
        required_tools = {
            "jq": {
                "min_version": "1.6",
                "check_cmd": ["jq", "--version"],
                "install_hint": "Install via: brew install jq (macOS) or apt-get install jq (Ubuntu)"
            },
            "yq": {
                "min_version": "4.0",
                "check_cmd": ["yq", "--version"],
                "install_hint": "Install via: brew install yq (macOS) or snap install yq (Ubuntu)"
            }
        }
        
        missing_tools = []
        incompatible_tools = []
        
        for tool_name, tool_config in required_tools.items():
            # Check if tool exists
            if not shutil.which(tool_name):
                missing_tools.append({
                    "name": tool_name,
                    "hint": tool_config["install_hint"]
                })
                continue
            
            # Check version compatibility
            try:
                result = subprocess.run(
                    tool_config["check_cmd"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode != 0:
                    incompatible_tools.append({
                        "name": tool_name,
                        "reason": f"Version check failed: {result.stderr}",
                        "hint": tool_config["install_hint"]
                    })
            except subprocess.TimeoutExpired:
                incompatible_tools.append({
                    "name": tool_name,
                    "reason": "Version check timed out",
                    "hint": tool_config["install_hint"]
                })
            except Exception as e:
                incompatible_tools.append({
                    "name": tool_name,
                    "reason": f"Version check error: {e}",
                    "hint": tool_config["install_hint"]
                })
        
        # Report errors with actionable guidance
        if missing_tools or incompatible_tools:
            error_msg = "Bootstrap runtime dependencies not satisfied:\n\n"
            
            if missing_tools:
                error_msg += "Missing tools:\n"
                for tool in missing_tools:
                    error_msg += f"  - {tool['name']}: {tool['hint']}\n"
            
            if incompatible_tools:
                error_msg += "\nIncompatible tools:\n"
                for tool in incompatible_tools:
                    error_msg += f"  - {tool['name']}: {tool['reason']}\n"
                    error_msg += f"    {tool['hint']}\n"
            
            error_msg += "\nThe ZeroTouch bootstrap requires these tools for script execution."
            
            raise RuntimeDependencyError(error_msg)
    
    def extract_all_scripts(self, stages: List[Dict], temp_dir: Path) -> Dict[str, str]:
        """Extract all referenced scripts and context files to secure temp directory"""
        script_map = {}
        script_resolver = ScriptResolver(self.adapter_registry)
        
        for stage in stages:
            script_uri = stage["script"]
            
            # Resolve URI to embedded script content
            adapter_name, script_name = script_uri.split("://")
            adapter = self.adapter_registry.get_adapter(adapter_name)
            script_content = adapter.get_embedded_script(script_name)
            
            # Write script to secure temp location
            script_path = temp_dir / "scripts" / adapter_name / script_name
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(script_content)
            script_path.chmod(0o755)
            
            # Write context file if script has context_data
            script_ref = self._find_script_ref_for_stage(adapter, stage)
            if script_ref and script_ref.context_data:
                context_path = temp_dir / "context" / adapter_name / f"{script_name}.context.json"
                context_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Resolve environment variables in context data
                resolved_context = self._resolve_context_vars(script_ref.context_data)
                context_path.write_text(json.dumps(resolved_context, indent=2))
                
                # Map stage name to script path + context path
                script_map[stage["name"]] = {
                    "script": str(script_path),
                    "context": str(context_path)
                }
            else:
                # Map stage name to physical path only
                script_map[stage["name"]] = {"script": str(script_path)}
        
        return script_map
    
    def _find_script_ref_for_stage(self, adapter: PlatformAdapter, stage: Dict) -> Optional[ScriptReference]:
        """Find ScriptReference for a given stage"""
        all_scripts = (
            adapter.pre_work_scripts() +
            adapter.post_work_scripts() +
            adapter.validation_scripts()
        )
        
        for script_ref in all_scripts:
            if script_ref.uri == stage["script"]:
                return script_ref
        
        return None
    
    def _resolve_context_vars(self, context_data: Dict) -> Dict:
        """Resolve environment variable references in context data"""
        import os
        import re
        
        def resolve_value(value):
            if isinstance(value, str):
                # Replace $VAR or ${VAR} with environment variable
                return re.sub(
                    r'\$\{?(\w+)\}?',
                    lambda m: os.environ.get(m.group(1), m.group(0)),
                    value
                )
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(item) for item in value]
            return value
        
        return resolve_value(context_data)
    
    def validate_lock_file(self):
        """Validate lock file before bootstrap"""
        lock_file = self.repo_root / "platform" / "lock.json"
        
        if not lock_file.exists():
            raise LockFileNotFoundError("Lock file not found. Run 'ztc render' first.")
        
        lock_data = json.loads(lock_file.read_text())
        
        # Validate environment matches
        if lock_data.get("environment") != self.env:
            raise EnvironmentMismatchError(
                f"Lock file environment '{lock_data.get('environment')}' "
                f"does not match --env '{self.env}'"
            )
        
        # Validate platform.yaml hash
        platform_yaml = self.repo_root / "platform.yaml"
        current_hash = self.hash_file(platform_yaml)
        
        if current_hash != lock_data.get("platform_hash"):
            raise PlatformModifiedError(
                "platform.yaml has been modified since render. "
                "Run 'ztc render' to regenerate artifacts."
            )
    
    def prepare_env_vars(self) -> Dict[str, str]:
        """Prepare environment variables for bootstrap"""
        platform_yaml = yaml.safe_load((self.repo_root / "platform.yaml").read_text())
        
        env_vars = {
            "ENV": self.env,
            "REPO_ROOT": str(self.repo_root),
            "SKIP_CACHE": "true" if self.skip_cache else "false"
        }
        
        # Extract adapter-specific env vars (required fields)
        adapters = platform_yaml["adapters"]  # Required field
        for adapter_name, adapter_config in adapters.items():
            if adapter_name == "hetzner":
                env_vars["HCLOUD_TOKEN"] = adapter_config["api_token"]  # Required field
            elif adapter_name == "talos":
                env_vars["SERVER_IP"] = adapter_config["nodes"][0]["ip"]
                # Additional env vars from adapter config
        
        return env_vars
```

### 5.2 Script Resolution (Removed - AOT Extraction)

The original design proposed runtime script resolution where `stage-executor.sh` would call back to the Python `ztc` binary during execution. This has been replaced with **Ahead-of-Time (AOT) Script Extraction** for correctness and performance:

**Original Approach (Removed):**
```bash
# stage-executor.sh would call:
SCRIPT_PATH=$(ztc_resolve_script "$STAGE_SCRIPT")  # Python startup overhead per stage
```

**New Approach (AOT Extraction):**
All scripts are extracted to a secure temporary directory before `stage-executor.sh` execution begins. The executor receives a `runtime_manifest.json` mapping stage names to physical script paths.

**Benefits:**
- Eliminates Python startup overhead (200-500ms per stage)
- Removes runtime dependency on Python environment
- Improves reliability (no mid-execution Python failures)
- Maintains security via `tempfile.TemporaryDirectory()` with 0700 permissions

### 5.3 Stage Executor Integration

The engine generates `production.yaml` compatible with the existing `stage-executor.sh`:

```yaml
# Generated bootstrap/pipeline/production.yaml
mode: production
total_steps: 10

stages:
  # Hetzner adapter stages
  - name: enable_rescue_mode
    description: Enable rescue mode for all servers
    script: hetzner://enable-rescue-mode.sh
    cache_key: enable_rescue_mode
    required: true

  # Cilium adapter stages (manifests embedded in Talos)
  # No install stages - Cilium embedded in Talos config

  # Talos adapter stages
  - name: embed_network_manifests
    description: Embed Gateway API CRDs and Cilium CNI in Talos config
    script: talos://02-embed-network-manifests.sh
    cache_key: embed_network_manifests
    required: true

  - name: install_talos
    description: Install Talos OS on bare-metal server
    script: talos://03-install-talos.sh
    cache_key: install_talos
    required: true
    context_file: talos/03-install-talos.sh.context.json  # Context data instead of args

  - name: bootstrap_talos
    description: Bootstrap Talos cluster and generate credentials
    script: talos://04-bootstrap-talos.sh
    cache_key: bootstrap_talos
    required: true
    context_file: talos/04-bootstrap-talos.sh.context.json

  - name: add_worker_nodes
    description: Add worker nodes to cluster
    script: talos://05-add-worker-nodes.sh
    cache_key: add_worker_nodes
    required: false
    context_file: talos/05-add-worker-nodes.sh.context.json
    skip_if_empty: WORKER_NODES

  # Cilium adapter post-work stages
  - name: wait_cilium
    description: Wait for Cilium CNI to be ready
    script: cilium://wait-cilium.sh
    cache_key: wait_cilium
    required: true

  - name: wait_gateway_api
    description: Validate Gateway API CRDs readiness
    script: cilium://wait-gateway-api.sh
    cache_key: wait_gateway_api
    required: true

  # Validation stages (always run)
  - name: validate_cluster
    description: Verify nodes joined cluster
    script: talos://validate-cluster.sh
    cache_key: null  # Always run
    required: true

  - name: validate_cni
    description: Verify pod networking
    script: cilium://validate-cni.sh
    cache_key: null  # Always run
    required: true

  - name: validate_server_ids
    description: Verify providerID injection
    script: hetzner://validate-server-ids.sh
    cache_key: null  # Always run
    required: true
```

**Stage Executor Modifications:**

The existing `stage-executor.sh` needs minimal modifications to support script maps and context files:

```bash
# stage-executor.sh modification
SCRIPT_MAP_FILE=""
CONTEXT_DIR=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --script-map)
            SCRIPT_MAP_FILE="$2"
            shift 2
            ;;
        --context-dir)
            CONTEXT_DIR="$2"
            shift 2
            ;;
        *)
            PIPELINE_YAML="$1"
            shift
            ;;
    esac
done

resolve_script_path() {
    local stage_name="$1"
    
    # Look up physical path from runtime manifest (required)
    if [[ -z "$SCRIPT_MAP_FILE" ]]; then
        echo "ERROR: SCRIPT_MAP_FILE not provided" >&2
        exit 1
    fi
    
    jq -r ".\"$stage_name\"" "$SCRIPT_MAP_FILE"
}

execute_stage() {
    local stage_name="$1"
    local context_file="$2"  # Optional context file path
    
    SCRIPT_PATH=$(resolve_script_path "$stage_name")
    
    # Set ZTC_CONTEXT_FILE if context file specified
    if [[ -n "$context_file" && -n "$CONTEXT_DIR" ]]; then
        export ZTC_CONTEXT_FILE="$CONTEXT_DIR/$context_file"
        
        if [[ ! -f "$ZTC_CONTEXT_FILE" ]]; then
            echo "ERROR: Context file not found: $ZTC_CONTEXT_FILE" >&2
            exit 1
        fi
    fi
    
    # Execute script (reads context via $ZTC_CONTEXT_FILE)
    bash "$SCRIPT_PATH"
}

# Usage in stage execution loop
CONTEXT_FILE=$(yq eval ".stages[$i].context_file // \"\"" "$PIPELINE_YAML")
execute_stage "$STAGE_NAME" "$CONTEXT_FILE"
```

**Example Script Reading Context:**

```bash
#!/usr/bin/env bash
# talos/03-install-talos.sh
set -euo pipefail

# Read context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

# Parse JSON with jq (safer than CLI args)
SERVER_IP=$(jq -r '.server_ip' "$ZTC_CONTEXT_FILE")
USER=$(jq -r '.user' "$ZTC_CONTEXT_FILE")
PASSWORD=$(jq -r '.password' "$ZTC_CONTEXT_FILE")
CONFIRM=$(jq -r '.confirm_destructive' "$ZTC_CONTEXT_FILE")

if [[ "$CONFIRM" != "true" ]]; then
    echo "ERROR: Destructive operation not confirmed" >&2
    exit 1
fi

echo "Installing Talos on $SERVER_IP as $USER"
# ... installation logic
```

**Benefits of Context Files over CLI Args:**
- No shell escaping issues with special characters
- Supports complex data structures (arrays, nested objects)
- Type safety via JSON schema validation
- Easier debugging (inspect context.json directly)
- Prevents argument injection attacks

## 6. Lock File Mechanism

### 6.1 Lock File Structure

```json
{
  "platform_hash": "abc123...",
  "ztc_version": "0.1.0",
  "artifacts_hash": "def456...",
  "environment": "production",
  "timestamp": "2026-02-12T10:30:00Z",
  "adapters": {
    "hetzner": {
      "version": "1.0.0",
      "type": "hetzner",
      "config_hash": "ghi789..."
    },
    "cilium": {
      "version": "1.0.0",
      "type": "cilium",
      "config_hash": "jkl012..."
    },
    "talos": {
      "version": "1.0.0",
      "type": "talos",
      "config_hash": "mno345..."
    }
  }
}
```

### 6.2 Lock File Generation

```python
# ztc/engine/lock.py
import hashlib
import json
from datetime import datetime
from pathlib import Path

class LockFileGenerator:
    def generate(self, platform_yaml: Path, generated_dir: Path, adapters: List[PlatformAdapter]) -> Dict:
        """Generate lock file from render results"""
        return {
            "platform_hash": self.hash_file(platform_yaml),
            "ztc_version": self.get_cli_version(),
            "artifacts_hash": self.hash_directory(generated_dir),
            "environment": "production",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "adapters": self.generate_adapter_metadata(adapters)
        }
    
    def hash_file(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file"""
        return hashlib.sha256(file_path.read_bytes()).hexdigest()
    
    def hash_directory(self, dir_path: Path) -> str:
        """Calculate SHA256 hash of directory tree"""
        hasher = hashlib.sha256()
        
        for file_path in sorted(dir_path.rglob("*")):
            if file_path.is_file() and not self.should_ignore(file_path):
                hasher.update(file_path.read_bytes())
        
        return hasher.hexdigest()
    
    def should_ignore(self, file_path: Path) -> bool:
        """Check if file should be ignored in hash calculation"""
        ignore_patterns = [".DS_Store", "*.swp", "*~"]
        return any(file_path.match(pattern) for pattern in ignore_patterns)
    
    def generate_adapter_metadata(self, adapters: List[PlatformAdapter]) -> Dict:
        """Generate adapter metadata for lock file"""
        metadata = {}
        
        for adapter in adapters:
            adapter_meta = adapter.load_metadata()
            metadata[adapter.name] = {
                "version": adapter_meta["version"],
                "type": adapter.name,
                "config_hash": self.hash_dict(adapter.config)
            }
        
        return metadata
    
    def hash_dict(self, data: Dict) -> str:
        """Calculate hash of dictionary"""
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def hash_file(self, file_path: Path, chunk_size: int = 4096) -> str:
        """Calculate SHA256 hash of file using streaming (memory-safe)
        
        Args:
            file_path: Path to file
            chunk_size: Bytes to read per iteration (default 4KB)
        
        Returns:
            Hex-encoded SHA256 hash
        
        Note:
            Uses streaming to maintain constant memory usage regardless of file size.
            Critical for bootstrap tools that may process large binaries/ISOs.
        """
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
```

## 7. Versions Matrix

### 7.1 Embedded versions.yaml (Required)

```yaml
# Embedded in CLI binary (ztc/versions.yaml)
# All versions must be explicitly defined - no runtime discovery
components:
  talos:
    supported_versions:
      - v1.10.x
      - v1.11.5
    default_version: v1.11.5
    artifacts:
      v1.11.5:
        factory_image_id: "376567988ad370138ad8b2698212367b8edcb69b5fd68c80be1f2ec7d603b4ba"
        image_url: "https://factory.talos.dev/image/{factory_image_id}/{version}/metal-amd64.raw.xz"
  
  cilium:
    supported_versions:
      - v1.16.x
      - v1.17.x
      - v1.18.5
    default_version: v1.18.5
    artifacts:
      v1.18.5:
        operator_image: "quay.io/cilium/operator-generic:v1.18.5@sha256:36c3f6f14c8ced7f45b40b0a927639894b44269dd653f9528e7a0dc363a4eb99"
        agent_image: "quay.io/cilium/cilium:v1.18.5"
  
  hetzner:
    api_version: v1
    base_url: "https://api.hetzner.cloud/v1"

# Remote versions URL (optional update mechanism)
remote_versions_url: "https://versions.ztc.dev/versions.yaml"
remote_versions_signature_url: "https://versions.ztc.dev/versions.yaml.sig"
```

### 7.2 Version Query Interface with Async Background Fetch and Error Logging

```python
# ztc/versions.py
import asyncio
import aiohttp
import logging
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key

logger = logging.getLogger(__name__)

class VersionRegistry:
    def __init__(self):
        self.embedded_versions = self.load_embedded_versions()
        self.remote_versions = None
        self.public_key = self.load_public_key()
        self._fetch_task = None  # Background fetch task
        self._last_error = None  # Store last fetch error for observability
        self._version_source = "embedded"  # Track which source was used
    
    def load_embedded_versions(self) -> Dict:
        """Load versions.yaml embedded in CLI binary"""
        versions_path = Path(__file__).parent / "versions.yaml"
        return yaml.safe_load(versions_path.read_text())
    
    def load_public_key(self):
        """Load public key for signature verification"""
        key_path = Path(__file__).parent / "ztc_public_key.pem"
        return load_pem_public_key(key_path.read_bytes())
    
    def start_background_fetch(self):
        """Start non-blocking background fetch of remote versions
        
        CRITICAL: This creates a task but does NOT guarantee completion.
        Always call get_versions_async() with explicit await to ensure deterministic behavior.
        """
        if self._fetch_task is None:
            self._fetch_task = asyncio.create_task(self._fetch_remote_async())
    
    async def get_versions_async(self, timeout: float = 2.0) -> Dict:
        """Get versions with explicit await on remote fetch (correctness-first)
        
        Args:
            timeout: Max time to wait for remote fetch (default 2s)
        
        Returns:
            Merged versions (remote + embedded) if remote succeeds, embedded-only on timeout/failure
        
        Behavior:
            - If fetch task not started, starts it and awaits with timeout
            - If fetch task already running, awaits its completion with timeout
            - On timeout/failure, falls back to embedded versions with explicit user notification
            - Tracks version source for transparency (self._version_source)
        
        Correctness Guarantee:
            User is explicitly notified which version source is used, preventing silent
            inconsistencies across team members due to network conditions.
        """
        # Ensure fetch task is started
        if self._fetch_task is None:
            self._fetch_task = asyncio.create_task(self._fetch_remote_async())
        
        try:
            # Explicitly await the fetch task with timeout (no "likely" assumptions)
            remote = await asyncio.wait_for(self._fetch_task, timeout=timeout)
            if remote:
                logger.info("Successfully fetched remote versions")
                self._version_source = "remote"
                return self._merge_versions(self.embedded_versions, remote)
        except asyncio.TimeoutError:
            logger.warning(f"Version check timed out after {timeout}s - using embedded fallback")
            self._last_error = f"Timeout after {timeout}s"
            self._version_source = "embedded (timeout)"
        except Exception as e:
            logger.warning(f"Version check failed ({type(e).__name__}: {e}) - using embedded fallback")
            self._last_error = f"{type(e).__name__}: {e}"
            self._version_source = f"embedded (error: {type(e).__name__})"
        
        return self.embedded_versions
    
    def get_versions(self) -> Dict:
        """Synchronous version getter (uses embedded only, no blocking)"""
        return self.embedded_versions
    
    def get_version_source(self) -> str:
        """Get the source of versions used (for user transparency)"""
        return self._version_source
    
    def get_last_error(self) -> Optional[str]:
        """Get last version fetch error for display in CLI summary"""
        return self._last_error
    
    async def _fetch_remote_async(self) -> Optional[Dict]:
        """Async fetch and verify remote versions.yaml"""
        try:
            remote_url = self.embedded_versions.get("remote_versions_url")
            sig_url = self.embedded_versions.get("remote_versions_signature_url")
            
            if not remote_url:
                logger.debug("No remote_versions_url configured")
                return None
            
            async with aiohttp.ClientSession() as session:
                # Fetch versions file
                async with session.get(remote_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    response.raise_for_status()
                    versions_content = await response.read()
                
                # Fetch signature
                async with session.get(sig_url, timeout=aiohttp.ClientTimeout(total=5)) as sig_response:
                    sig_response.raise_for_status()
                    signature = await sig_response.read()
            
            # Verify signature
            if self._verify_signature(versions_content, signature):
                return yaml.safe_load(versions_content)
            else:
                logger.warning("Remote versions signature verification failed")
                return None
        
        except aiohttp.ClientError as e:
            logger.debug(f"Network error fetching remote versions: {e}")
            return None
        except Exception as e:
            logger.debug(f"Unexpected error fetching remote versions: {e}")
            return None
    
    def _verify_signature(self, content: bytes, signature: bytes) -> bool:
        """Verify cryptographic signature of remote versions file"""
        try:
            self.public_key.verify(
                signature,
                content,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception as e:
            logger.debug(f"Signature verification failed: {e}")
            return False
    
    def _merge_versions(self, embedded: Dict, remote: Dict) -> Dict:
        """Merge remote versions with embedded (remote takes precedence)"""
        merged = embedded.copy()
        
        # Raises KeyError if 'components' missing in remote - remote must be valid
        for component, component_data in remote["components"].items():
            if component in merged["components"]:
                # Merge component data (remote overrides embedded)
                merged["components"][component].update(component_data)
            else:
                # New component from remote
                merged["components"][component] = component_data
        
        return merged
    
    def get_supported_versions(self, component: str) -> List[str]:
        """Get supported versions for component
        
        Raises:
            KeyError: If component not found in versions.yaml
        """
        versions = self.get_versions()
        return versions["components"][component]["supported_versions"]
    
    def get_default_version(self, component: str) -> str:
        """Get default version for component
        
        Raises:
            KeyError: If component not found in versions.yaml
        """
        versions = self.get_versions()
        return versions["components"][component]["default_version"]
    
    def get_artifact(self, component: str, version: str, artifact_key: str) -> str:
        """Get artifact URL/SHA for specific version
        
        Raises:
            KeyError: If component, version, or artifact_key not found
        """
        versions = self.get_versions()
        return versions["components"][component]["artifacts"][version][artifact_key]
```

**CLI Integration with Explicit User Notification:**

```python
# ztc/cli.py
@app.command()
async def init(resume: bool = typer.Option(False, "--resume")):
    """Initialize platform configuration via interactive prompts"""
    console = Console()
    registry = VersionRegistry()
    
    # Start background version fetch (non-blocking)
    console.print("[dim]Checking for latest versions...[/dim]")
    registry.start_background_fetch()
    
    # User answers prompts while fetch happens in background
    workflow = InitWorkflow(console, adapter_registry)
    config = await workflow.run(resume)
    
    # Explicitly await version fetch with timeout (correctness guarantee)
    versions = await registry.get_versions_async(timeout=2.0)
    
    # CRITICAL: Notify user which version source was used
    version_source = registry.get_version_source()
    if "embedded" in version_source:
        if "timeout" in version_source:
            console.print(
                "[yellow]⚠[/yellow] Using embedded versions (remote check timed out). "
                "Team members may see different versions if their network is faster."
            )
        elif "error" in version_source:
            console.print(
                f"[yellow]⚠[/yellow] Using embedded versions (remote check failed: {registry.get_last_error()}). "
                "Run 'ztc update-versions' to sync with latest."
            )
        else:
            console.print("[dim]Using embedded versions (no remote configured)[/dim]")
    else:
        console.print("[green]✓[/green] Using latest remote versions")
    
    console.print("[green]✓[/green] Configuration complete")
```
    registry.start_background_fetch()
    
    # User answers prompts while fetch happens in background
    workflow = InitWorkflow(console, adapter_registry)
    config = await workflow.run(resume)
    
    # By the time we need versions, fetch likely completed
    # If not, timeout after 2s and use embedded
    versions = await registry.get_versions_async(timeout=2.0)
    
    console.print("[green]✓[/green] Configuration complete")
```

**Alternative: Explicit Update Command:**

```python
@app.command()
async def update_versions():
    """Explicitly update versions.yaml from remote source"""
    console = Console()
    registry = VersionRegistry()
    
    with console.status("[bold blue]Fetching latest versions..."):
        remote = await registry._fetch_remote_async()
    
    if remote:
        # Cache remote versions locally for offline use
        cache_path = Path.home() / ".ztc" / "versions_cache.yaml"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(yaml.dump(remote))
        console.print("[green]✓[/green] Versions updated successfully")
    else:
        console.print("[red]✗[/red] Failed to fetch remote versions")
```

## 8. Error Handling & Validation

### 8.1 Validation Pipeline

```python
# ztc/validation/validator.py
class PlatformValidator:
    def validate_platform_yaml(self, platform_yaml: Dict):
        """Validate platform.yaml structure"""
        # Schema validation
        schema = self.load_platform_schema()
        jsonschema.validate(platform_yaml, schema)
        
        # Adapter-specific validation (required field)
        for adapter_name, adapter_config in platform_yaml["adapters"].items():
            adapter = self.adapter_registry.get(adapter_config["type"])
            adapter_schema = adapter.load_schema()
            jsonschema.validate(adapter_config, adapter_schema)
    
    def validate_generated_artifacts(self, generated_dir: Path, adapters: List[PlatformAdapter]):
        """Validate generated artifacts against output schemas"""
        for adapter in adapters:
            output = self.context.get_output(adapter.name)
            output_schema = adapter.load_output_schema()
            jsonschema.validate(output.data, output_schema)
    
    def validate_lock_file(self, lock_file: Path, platform_yaml: Path):
        """Validate lock file integrity"""
        lock_data = json.loads(lock_file.read_text())
        
        # Validate platform hash
        current_hash = self.hash_file(platform_yaml)
        if current_hash != lock_data["platform_hash"]:
            raise LockFileValidationError("platform.yaml modified since render")
        
        # Validate artifacts hash
        generated_dir = Path("platform/generated")
        current_artifacts_hash = self.hash_directory(generated_dir)
        if current_artifacts_hash != lock_data["artifacts_hash"]:
            raise LockFileValidationError("Generated artifacts modified since render")
```

### 8.2 Error Messages

```python
# ztc/errors.py
class ZTCError(Exception):
    """Base exception for ZTC errors"""
    def __init__(self, message: str, help_text: Optional[str] = None):
        self.message = message
        self.help_text = help_text
        super().__init__(message)

class MissingCapabilityError(ZTCError):
    """Raised when required capability not provided by any adapter"""
    def __init__(self, adapter_name: str, capability: str):
        message = f"Adapter '{adapter_name}' requires capability '{capability}' but no adapter provides it"
        help_text = f"Add an adapter that provides '{capability}' to platform.yaml"
        super().__init__(message, help_text)

class LockFileValidationError(ZTCError):
    """Raised when lock file validation fails"""
    def __init__(self, reason: str):
        message = f"Lock file validation failed: {reason}"
        help_text = "Run 'ztc render' to regenerate artifacts"
        super().__init__(message, help_text)

class RuntimeDependencyError(ZTCError):
    """Raised when required runtime dependencies are missing or incompatible
    
    This error upholds the ZeroTouch promise by failing fast before bootstrap
    execution, preventing mid-flight crashes due to missing tools like jq/yq.
    """
    def __init__(self, message: str):
        help_text = (
            "Install missing dependencies before running 'ztc bootstrap'. "
            "Run 'ztc doctor' to check all dependencies."
        )
        super().__init__(message, help_text)
```

## 9. Testing Strategy

### 9.1 Unit Tests

```python
# tests/unit/test_adapter_interface.py
def test_talos_adapter_required_inputs():
    adapter = TalosAdapter({})
    inputs = adapter.get_required_inputs()
    
    assert len(inputs) > 0
    assert any(inp.name == "version" for inp in inputs)
    assert any(inp.name == "cluster_name" for inp in inputs)

def test_dependency_resolution():
    resolver = DependencyResolver()
    adapters = [HetznerAdapter({}), CiliumAdapter({}), TalosAdapter({})]
    
    resolved = resolver.resolve(adapters)
    
    # Hetzner should be first (foundation, no dependencies)
    assert resolved[0].name == "hetzner"
    # Talos should be before Cilium (Cilium requires kubernetes-api)
    talos_idx = next(i for i, a in enumerate(resolved) if a.name == "talos")
    cilium_idx = next(i for i, a in enumerate(resolved) if a.name == "cilium")
    assert talos_idx < cilium_idx
```

### 9.2 Integration Tests

```python
# tests/integration/test_end_to_end.py
def test_init_render_bootstrap_flow(tmp_path):
    # 1. Run ztc init (mocked prompts)
    with mock_prompts({
        "cloud_provider": "hetzner",
        "api_token": "test_token",
        "network_tool": "cilium",
        "os": "talos"
    }):
        result = cli_runner.invoke(app, ["init"])
        assert result.exit_code == 0
    
    # 2. Verify platform.yaml generated
    platform_yaml = tmp_path / "platform.yaml"
    assert platform_yaml.exists()
    
    # 3. Run ztc render
    result = cli_runner.invoke(app, ["render"])
    assert result.exit_code == 0
    
    # 4. Verify artifacts generated
    assert (tmp_path / "platform/generated/os/talos/nodes").exists()
    assert (tmp_path / "platform/lock.json").exists()
    
    # 5. Run ztc validate
    result = cli_runner.invoke(app, ["validate"])
    assert result.exit_code == 0
```

## 10. Deployment & Distribution

### 10.1 Poetry Packaging

```toml
# pyproject.toml
[tool.poetry]
name = "ztc"
version = "0.1.0"
description = "ZeroTouch Composition Engine - Bare-metal Kubernetes bootstrap"
authors = ["ZeroTouch Team"]

[tool.poetry.dependencies]
python = "^3.11"
typer = "^0.12.0"
rich = "^13.0.0"
pyyaml = "^6.0"
jsonschema = "^4.0"
pydantic = "^2.0"
jinja2 = "^3.0"

[tool.poetry.scripts]
ztc = "ztc.cli:app"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

### 10.2 Binary Distribution

```bash
# Build standalone binary with PyInstaller
poetry run pyinstaller \
    --onefile \
    --name ztc \
    --add-data "ztc/adapters:adapters" \
    --add-data "ztc/versions.yaml:." \
    ztc/cli.py

# Result: dist/ztc (single executable with embedded adapters)
```

## 11. Future Extensibility

### 11.1 Adding New Adapters (Phase 2+)

To add a new adapter (e.g., ArgoCD):

1. Create adapter directory: `ztc/adapters/argocd/`
2. Implement `PlatformAdapter` interface
3. Define `adapter.yaml` metadata
4. Create `schema.json` and `output-schema.json`
5. Embed scripts in `scripts/` directory
6. Create Jinja2 templates in `templates/` directory
7. Register adapter in `AdapterRegistry`
8. Update `versions.yaml` with supported versions

### 11.2 Adapter Marketplace (Future)

Future phases could support external adapter plugins:

```bash
# Install community adapter
ztc adapter install community/flux-adapter

# List installed adapters
ztc adapter list

# Update adapter
ztc adapter update flux-adapter
```

## 12. Security Considerations

### 12.1 Sensitive Data Handling

- API tokens must be provided via environment variables or runtime prompts (never stored in platform.yaml)
- Passwords never written to disk (runtime prompts only)
- Lock file must not contain sensitive data
- Generated artifacts reviewed before Git commit
- No fallback mechanisms for missing credentials - fail fast with clear error messages

### 12.2 Script Execution Isolation

- Scripts execute in secure temporary directories via `tempfile.TemporaryDirectory()`
- Temporary directories created with 0700 permissions (owner-only access)
- Automatic cleanup via context manager (even on process crash/signal)
- Script URIs prevent direct filesystem access
- Embedded scripts validated at build time
- AOT extraction eliminates runtime code injection risks

**Secure Temporary Directory Pattern:**
```python
import tempfile

class ScriptExecutor:
    def execute_with_isolation(self, scripts: List[str]):
        """Execute scripts in secure isolated environment"""
        # Context manager ensures cleanup even on crash
        with tempfile.TemporaryDirectory(prefix="ztc-secure-") as secure_dir:
            # secure_dir has 0700 permissions automatically
            for script in scripts:
                script_path = Path(secure_dir) / script.name
                script_path.write_text(script.content)
                script_path.chmod(0o755)
                
                # Execute in isolated directory
                subprocess.run([str(script_path)], cwd=secure_dir)
            
            # Automatic cleanup on context exit
```

**Security Benefits:**
- No predictable temp paths (UUID-based via tempfile)
- No world-readable permissions on shared systems
- Automatic cleanup prevents temp file leakage
- Signal-safe cleanup (SIGTERM, SIGINT handled)

## 13. Performance Optimization

### 13.1 Render Performance

- AsyncIO support for I/O-bound adapters (Hetzner API calls, network operations)
- Template caching (Jinja2 compiled templates)
- Lock file prevents unnecessary re-renders
- Incremental rendering (only changed adapters) - future phase

**AsyncIO Benefits for 19 Adapters:**
- Hetzner API lookups don't block Cilium template rendering
- Multiple API-heavy adapters can execute concurrently
- Reduces total render time from sum(adapter_times) to max(adapter_times) for independent adapters

### 13.2 Bootstrap Performance

- AOT script extraction eliminates Python startup overhead (200-500ms per stage)
- Stage caching reduces redundant operations
- Configurable timeouts per stage
- Rich progress bars for long operations
- Parallel stage execution (future phase, requires dependency graph analysis)

**Performance Comparison:**

| Approach | 20 Stages | Overhead |
|----------|-----------|----------|
| Runtime Resolution (Old) | 20 × 300ms = 6s | Python startup per stage |
| AOT Extraction (New) | 1 × 300ms = 0.3s | Python startup once |
| **Savings** | **5.7 seconds** | **95% reduction** |


## 14. Phase 2+ Architectural Enhancements (Deferred)

The following improvements were identified in technical audits but deferred to Phase 2+ as they optimize for scale beyond the current 3-adapter scope. These are documented here for future reference.

### 14.1 Capability-Based Validation Strategy

**Current State:** Adapters use `get_invalid_fields()` to inspect upstream config and determine invalid fields.

**Issue:** Creates implicit coupling between adapters. Cilium must know Talos config structure to invalidate `embedded_mode`.

**Proposed Enhancement:**
- Adapters validate against Capability objects, not upstream config dicts
- Engine detects Capability contract violations and triggers re-validation
- Reduces cross-adapter coupling as system scales to 19+ adapters

```python
# Future implementation
def validate_requirements(self, ctx: ContextSnapshot) -> ValidationResult:
    k8s_cap = ctx.get_capability_data(Capability.KUBERNETES_API)
    if self.config.embedded_mode and not k8s_cap.supports_embedded_cni:
        return ValidationResult.invalid(
            fields=["embedded_mode"],
            reason="Current OS does not support embedded CNI"
        )
    return ValidationResult.valid()
```

**Defer Rationale:** Current differential validation works well for 3 adapters. Complexity cost outweighs benefits until adapter count increases.

### 14.2 Decentralized Adapter Versioning

**Current State:** Single `versions.yaml` embedded in CLI binary contains all adapter versions.

**Issue:** Updating one adapter's version requires rebuilding entire ZTC binary. Prevents independent adapter development.

**Proposed Enhancement:**
- Each adapter package contains its own `versions.yaml`
- Global `versions.yaml` serves as override/pinning matrix
- `VersionRegistry` aggregates distributed files at runtime

**Defer Rationale:** Phase 1 has only 3 embedded adapters. This becomes critical when supporting external/community adapters in Phase 2+.

### 14.3 DAG Scheduler with Parallelization

**Current State:** Adapters grouped into 4 linear phases (foundation, networking, platform, services).

**Issue:** Independent adapters in same phase execute sequentially, blocking CPU/IO.

**Proposed Enhancement:**
- Build true DAG based solely on `requires` and `provides`
- Render time: Use `asyncio.gather` for independent branches
- Bootstrap time: Generate pipeline with parallel stage blocks

**Defer Rationale:** Phase 1's 3 adapters in linear phases is sufficient. Parallelization complexity justified when adapter count increases.

### 14.4 Component-Based Adapter Definition

**Current State:** `PlatformAdapter` combines UI, configuration, and operational logic in one class.

**Issue:** Violates Interface Segregation. Building Web UI or REST API would require carrying unused CLI-specific code.

**Proposed Enhancement:**
```python
class AdapterDefinition:
    config_schema: Type[BaseModel]  # Universal
    renderer: Renderer               # Universal
    operations: LifecycleManager     # Runtime
    ui_hints: Optional[UIProvider]   # CLI-specific (optional)
```

**Defer Rationale:** Phase 1 is CLI-only. Refactor when adding new interfaces (Web UI, REST API) in Phase 2+.

### 14.5 Scoped Jinja Environments

**Current State:** Single shared `Environment` with `PrefixLoader` for all adapters.

**Issue:** Shared filter/test registry could create invisible coupling if adapters register custom filters.

**Proposed Enhancement:**
- Maintain shared loader for performance
- Enforce namespace prefixes for filters/globals
- Use overlay environments if needed

**Defer Rationale:** Namespace collision risk is theoretical with 3 adapters. Enforce naming conventions now, refactor if issues arise.

### 14.6 ThreadPoolExecutor for Rendering

**Current State:** `render()` marked as `async` but Jinja2 rendering is CPU-bound, blocking asyncio loop.

**Issue:** While one adapter renders templates, others can't perform network I/O.

**Proposed Enhancement:**
```python
loop = asyncio.get_running_loop()
output = await loop.run_in_executor(None, adapter.render_sync, snapshot)
```

**Defer Rationale:** With 3 adapters, performance impact is minimal. Optimize when profiling shows bottlenecks at scale.

### 14.7 JIT Script Extraction

**Current State:** AOT extraction writes all scripts to disk before execution.

**Issue:** Maximizes "attack window" where secrets exist in plaintext on filesystem.

**Proposed Enhancement:**
- Keep resolution AOT (mapping names to resources)
- Delay extraction (writing to disk) until immediately before stage execution
- Delete immediately after stage completes

**Defer Rationale:** Current AOT + SecureTempDir + signal handling + vacuum command provides adequate security for Phase 1. JIT adds significant complexity.

### 14.8 Containerized Bootstrap Runtime

**Current State:** Bootstrap validates jq/yq presence on host machine.

**Issue:** Still relies on host environment having compatible versions.

**Proposed Enhancement:**
- Use standard "Bootstrap Container" (alpine with curl/jq/yq pre-installed)
- `ztc bootstrap` runs `docker run -v ... ztc-runner ...`
- Alternative: Embed static binaries of jq/yq in ZTC binary

**Defer Rationale:** Upfront validation provides adequate safety for Phase 1. Containerization adds Docker dependency and complexity. Consider for Phase 2+ if host environment issues arise.

---

**Review Cadence:** Revisit these enhancements when:
- Adapter count exceeds 10
- Community/external adapters are supported
- Non-CLI interfaces are added (Web UI, REST API)
- Performance profiling identifies bottlenecks
- Security audits recommend JIT extraction
