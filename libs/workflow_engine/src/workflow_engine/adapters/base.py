"""Base adapter interface"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Type
from pathlib import Path
from pydantic import BaseModel
from jinja2 import Environment
from enum import Enum
import importlib.resources
import warnings
from .operation_mode import OperationType, enforce_read_only


@dataclass
class InputPrompt:
    """Definition for interactive user input"""
    name: str
    prompt: str
    type: str  # choice, boolean, string, password, integer, json
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
    package: str                      # e.g., "workflow_engine.adapters.talos.scripts"
    resource: 'Enum'                  # Enum value (e.g., TalosScripts.INSTALL)
    description: str
    timeout: int = 300                # seconds
    context_data: Optional[Dict[str, Any]] = None  # Data passed via context.json (replaces args)
    secret_env_vars: Optional[Dict[str, str]] = None  # Secrets passed via environment variables
    args: Optional[List[str]] = None  # Deprecated: use context_data instead
    uri: str = field(init=False)      # Generated URI for backward compatibility
    
    def __post_init__(self):
        """Validate script existence immediately upon instantiation"""
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
        adapter_name = self.package.split('.')[-2]  # Extract from "workflow_engine.adapters.talos.scripts"
        self.uri = f"{adapter_name}://{self.resource.value}"
        
        # Warn if using deprecated args
        if self.args and self.context_data:
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
    args: Optional[List[str]] = None
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
    
    def get_cli_app(self):
        """Return Typer instance with adapter-specific commands
        
        Returns:
            typer.Typer instance with registered commands, or None if no CLI commands
        """
        return None


class PlatformAdapter(ABC):
    """Abstract base class for platform adapters"""
    
    def __init__(self, config: Dict[str, Any], jinja_env: Optional[Environment] = None):
        self.config = config
        self.name = self.load_metadata()["name"]
        self.phase = self.load_metadata()["phase"]
        self._jinja_env = jinja_env  # Shared environment from Engine
        self._platform_metadata: Dict[str, Any] = {}  # Store platform metadata (app_name, organization)
        self._all_adapters_config: Dict[str, Dict[str, Any]] = {}  # Store all adapters' config
    
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
        """Return list of interactive prompts for user input collection
        
        This is a READ operation - safe to call during workflow traversal.
        """
        pass
    
    def validate_upstream_context(self, current_config: Dict, full_platform_context: Dict) -> bool:
        """Validate if current adapter config is still valid given platform context changes
        
        Args:
            current_config: This adapter's current configuration
            full_platform_context: Complete platform.yaml context
        
        Returns:
            True if config is valid, False if it needs re-prompting
        
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
        """
        return []  # Default: no invalid fields (override in subclasses)
    
    @abstractmethod
    def init(self) -> List[ScriptReference]:
        """Return init-phase scripts (before cluster creation)
        
        Init scripts execute during 'ztc init' after configuration collection,
        before any cluster infrastructure exists. They should:
        
        - Perform external validation (API access, credentials)
        - Setup external resources (S3 buckets, DNS records)
        - NOT require cluster access (no kubectl, no Kubernetes API)
        - Be orchestrators that call sub-scripts for complex operations
        
        Execution Context:
        - Runs during 'ztc init' command
        - No cluster exists yet
        - Can access external APIs (GitHub, cloud providers, S3)
        - Receives context via $ZTC_CONTEXT_FILE environment variable
        - Secrets passed via environment variables (not in context file)
        
        Lifecycle Order:
        1. init() - Pre-cluster validation/setup (THIS METHOD)
        2. Cluster creation
        3. pre_work_scripts() - Pre-bootstrap setup
        4. bootstrap_scripts() - Core deployment
        5. post_work_scripts() - Post-deployment config
        6. validation_scripts() - Verify success
        
        Returns:
            List of ScriptReference objects with context_data and secret_env_vars
        
        Example:
            return [
                ScriptReference(
                    package="workflow_engine.adapters.github.scripts.init",
                    resource=GitHubScripts.VALIDATE_ACCESS,
                    description="Validate GitHub API access",
                    timeout=60,
                    context_data={"github_app_id": "123456"},
                    secret_env_vars={"GITHUB_APP_PRIVATE_KEY": "..."}
                )
            ]
        """
        pass
    
    @abstractmethod
    def pre_work_scripts(self) -> List[ScriptReference]:
        """Return pre-work scripts (before adapter bootstrap, e.g., rescue mode)"""
        pass
    
    @abstractmethod
    def bootstrap_scripts(self) -> List[ScriptReference]:
        """Return core adapter responsibility scripts (e.g., install OS, wait for CNI)"""
        pass
    
    @abstractmethod
    def post_work_scripts(self) -> List[ScriptReference]:
        """Return post-work scripts (after adapter bootstrap, e.g., additional config)"""
        pass
    
    @abstractmethod
    def validation_scripts(self) -> List[ScriptReference]:
        """Return verification scripts (validate deployment success)"""
        pass
    
    @abstractmethod
    async def render(self, ctx: 'ContextSnapshot') -> AdapterOutput:
        """Generate manifests, configs, and stage definitions (async for I/O operations)
        
        This is a MUTATE operation - must be deferred to completion phase.
        Should NOT be called during workflow traversal.
        
        Args:
            ctx: Immutable snapshot of platform context (read-only)
        
        Returns:
            AdapterOutput with manifests, stages, and capability data
        """
        pass
    
    def get_embedded_script(self, script_name: str) -> str:
        """Retrieve embedded script content by name using importlib.resources"""
        import importlib.resources
        
        # Get the adapter's package name (e.g., "workflow_engine.adapters.talos")
        adapter_package = self.__class__.__module__.rsplit('.', 1)[0]
        scripts_package = f"{adapter_package}.scripts"
        
        try:
            # Use importlib.resources for package-based access
            files = importlib.resources.files(scripts_package)
            script_file = files / script_name
            
            if script_file.is_file():
                return script_file.read_text()
            else:
                raise FileNotFoundError(
                    f"Script '{script_name}' not found in package '{scripts_package}'"
                )
        except (ModuleNotFoundError, AttributeError) as e:
            raise FileNotFoundError(
                f"Scripts package '{scripts_package}' not found: {e}"
            )
    
    def load_metadata(self) -> Dict[str, Any]:
        """Load adapter.yaml metadata"""
        import yaml
        metadata_path = Path(__file__).parent / "adapter.yaml"
        return yaml.safe_load(metadata_path.read_text())
    
    # Input Collection Customization Methods
    
    def set_platform_metadata(self, metadata: Dict[str, Any]) -> None:
        """Set platform metadata (app_name, organization) for use in suggestions
        
        Args:
            metadata: Dictionary containing platform metadata like app_name and organization
        
        Example:
            adapter.set_platform_metadata({"app_name": "myapp", "organization": "myorg"})
        """
        self._platform_metadata = metadata
    
    def set_all_adapters_config(self, config: Dict[str, Dict[str, Any]]) -> None:
        """Set configuration from all adapters for cross-adapter dependencies
        
        Args:
            config: Dictionary mapping adapter names to their configurations
        
        Example:
            adapter.set_all_adapters_config({"github": {"control_plane_repo_url": "..."}})
        """
        self._all_adapters_config = config
    
    def should_skip_field(self, field_name: str, current_config: Dict[str, Any]) -> bool:
        """Determine if a field should be skipped based on conditions
        
        Args:
            field_name: Name of the field being collected
            current_config: Configuration collected so far for this adapter
        
        Returns:
            True if field should be skipped, False otherwise
        
        Example:
            def should_skip_field(self, field_name, current_config):
                if field_name == "bgp_asn" and not current_config.get("bgp_enabled"):
                    return True
                return False
        """
        return False  # Default: never skip
    
    def derive_field_value(self, field_name: str, current_config: Dict[str, Any]) -> Optional[Any]:
        """Derive a field's value from other fields or adapters
        
        Args:
            field_name: Name of the field being collected
            current_config: Configuration collected so far for this adapter
        
        Returns:
            Derived value if derivable, None if should prompt user
        
        Example:
            def derive_field_value(self, field_name, current_config):
                if field_name == "s3_region" and "s3_endpoint" in current_config:
                    match = re.search(r'https?://([^.]+)\.', current_config["s3_endpoint"])
                    if match:
                        return match.group(1)
                return None
        """
        return None  # Default: no derivation
    
    def get_input_context(self, field_name: str, current_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Provide additional context for input collection
        
        Called before prompting user. Returns dict of additional data to include
        in the question (e.g., server_ips for nodes collection).
        
        Args:
            field_name: Name of the field being collected
            current_config: Current adapter's collected configuration
            
        Returns:
            Dict of additional context, or None
            
        Example:
            def get_input_context(self, field_name, current_config):
                if field_name == "nodes":
                    server_ips = self.get_cross_adapter_config("hetzner", "server_ips")
                    return {"server_ips": server_ips}
                return None
        """
        return None  # Default: no additional context
    
    def get_field_suggestion(self, field_name: str) -> Optional[str]:
        """Generate a suggestion for a field based on platform metadata
        
        Args:
            field_name: Name of the field being collected
        
        Returns:
            Suggested value as a string, or None if no suggestion
        
        Example:
            def get_field_suggestion(self, field_name):
                app_name = self._platform_metadata.get('app_name', '')
                if field_name == "s3_bucket_name" and app_name:
                    return f"{app_name}-bucket"
                return None
        """
        return None  # Default: no suggestion
    
    def collect_field_value(self, input_prompt: InputPrompt, current_config: Dict[str, Any]) -> Any:
        """Collect a field value with custom logic
        
        Args:
            input_prompt: The InputPrompt definition for this field
            current_config: Configuration collected so far for this adapter
        
        Returns:
            The collected value, or None to signal init.py should use standard collection logic
        
        Note:
            Override this method for special input handling (e.g., loading from files,
            iterative collection, custom validation). Default implementation returns None
            to signal init.py should use standard collection logic.
        
        Example:
            def collect_field_value(self, input_prompt, current_config):
                if input_prompt.name == "github_app_private_key":
                    # Load from .env.global file
                    return self._load_from_env_global("GIT_APP_PRIVATE_KEY")
                return None  # Use default collection
        """
        return None  # Default: use standard collection logic
    
    def get_cross_adapter_config(self, adapter_name: str, field_name: Optional[str] = None) -> Optional[Any]:
        """Access configuration from another adapter
        
        Args:
            adapter_name: Name of the adapter to get config from
            field_name: Specific field to get, or None for entire config
        
        Returns:
            Configuration value, or None if not available
        
        Example:
            def derive_field_value(self, field_name, current_config):
                if field_name == "platform_repo_url":
                    github_url = self.get_cross_adapter_config("github", "control_plane_repo_url")
                    if github_url:
                        return f"{github_url}.git"
                return None
        """
        if adapter_name not in self._all_adapters_config:
            return None
        
        adapter_config = self._all_adapters_config[adapter_name]
        if field_name is None:
            return adapter_config
        return adapter_config.get(field_name)
    
    async def get_dynamic_choices(
        self, 
        input_prompt: InputPrompt,
        context: Dict[str, Any]
    ) -> List[str]:
        """Fetch dynamic choices at runtime (e.g., AWS VPCs, Hetzner servers)
        
        This is a READ operation - safe to call during workflow traversal.
        Subclasses can override to provide dynamic choices based on context.
        
        Args:
            input_prompt: The input prompt requesting dynamic choices
            context: Current platform context for API calls
            
        Returns:
            List of choice values, or empty list if not applicable
        """
        # Enforce read-only restriction
        enforce_read_only(OperationType.READ)
        
        # Default: return static choices from input_prompt
        return input_prompt.choices or []
