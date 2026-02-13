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
    package: str                      # e.g., "ztc.adapters.talos.scripts"
    resource: 'Enum'                  # Enum value (e.g., TalosScripts.INSTALL)
    description: str
    timeout: int = 300                # seconds
    context_data: Optional[Dict[str, Any]] = None  # Data passed via context.json (replaces args)
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
        adapter_name = self.package.split('.')[-2]  # Extract from "ztc.adapters.talos.scripts"
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


class PlatformAdapter(ABC):
    """Abstract base class for platform adapters"""
    
    def __init__(self, config: Dict[str, Any], jinja_env: Optional[Environment] = None):
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
        
        Args:
            ctx: Immutable snapshot of platform context (read-only)
        
        Returns:
            AdapterOutput with manifests, stages, and capability data
        """
        pass
    
    def get_embedded_script(self, script_name: str) -> str:
        """Retrieve embedded script content by name using importlib.resources"""
        import importlib.resources
        
        # Get the adapter's package name (e.g., "ztc.adapters.talos")
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
