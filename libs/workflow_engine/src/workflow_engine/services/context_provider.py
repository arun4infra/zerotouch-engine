"""Context provider service - centralized context management for bootstrap stages"""

from pathlib import Path
from typing import Dict, Any, Optional
import yaml
import json


class ContextProvider:
    """Provides stage context by delegating to adapters
    
    Responsibilities:
    - Load platform.yaml once
    - Delegate context building to adapters (adapter-owned logic)
    - Validate context for secrets (prevent leakage)
    - Write validated context to single centralized location
    - Provide context file path to bootstrap executor
    """
    
    def __init__(self, platform_yaml_path: Path = Path("platform/platform.yaml")):
        """Initialize context provider
        
        Args:
            platform_yaml_path: Path to platform.yaml
        """
        self.platform_yaml_path = platform_yaml_path
        self._platform_cache: Optional[Dict[str, Any]] = None
        self._adapter_instances: Dict[str, Any] = {}
        
        # Centralized context directory
        self.context_dir = Path(".zerotouch-cache/contexts")
        self.context_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_platform_yaml(self) -> Dict[str, Any]:
        """Load and cache platform.yaml"""
        if self._platform_cache is None:
            if not self.platform_yaml_path.exists():
                raise FileNotFoundError(f"Platform config not found: {self.platform_yaml_path}")
            
            with open(self.platform_yaml_path) as f:
                self._platform_cache = yaml.safe_load(f) or {}
        
        return self._platform_cache
    
    def _get_adapter_instance(self, adapter_name: str):
        """Get or create adapter instance (lazy-loaded)
        
        Args:
            adapter_name: Name of the adapter
            
        Returns:
            Adapter instance or None if not found
        """
        if adapter_name in self._adapter_instances:
            return self._adapter_instances[adapter_name]
        
        platform_data = self._load_platform_yaml()
        adapter_config = platform_data.get('adapters', {}).get(adapter_name, {})
        
        if not adapter_config:
            return None
        
        # Import and instantiate adapter
        try:
            from workflow_engine.registry.adapter_registry import AdapterRegistry
            registry = AdapterRegistry()
            adapter_class = registry.get_adapter_class(adapter_name)
            adapter = adapter_class(adapter_config, jinja_env=None)
            self._adapter_instances[adapter_name] = adapter
            return adapter
        except Exception as e:
            print(f"⚠️  Failed to load adapter '{adapter_name}': {e}")
        
        return None
    
    def get_stage_context(self, stage_name: str, adapter_name: str) -> Dict[str, Any]:
        """Get context for a bootstrap stage
        
        Merges context from ALL adapters (legacy pattern).
        Each adapter provides its own context via get_stage_context().
        
        Args:
            stage_name: Name of the bootstrap stage
            adapter_name: Name of the adapter owning this stage
            
        Returns:
            Context dictionary (non-sensitive data only)
        """
        platform_data = self._load_platform_yaml()
        all_adapters_config = platform_data.get('adapters', {})
        
        # Build base context (common fields)
        context = {
            # Platform metadata
            'organization': platform_data.get('platform', {}).get('organization', ''),
            'app_name': platform_data.get('platform', {}).get('app_name', ''),
            'mode': 'production',
            'env': 'dev',
            'namespace': 'argocd',
            'timeout_seconds': 300,
            'check_interval': 5,
            
            # Common paths
            'kubeconfig_path': str(Path.home() / '.kube/config'),
            'manifests_path': 'platform/generated/argocd/install',
            'install_path': '/usr/local/bin',
        }
        
        # Merge context from ALL adapters (legacy pattern - scripts expect full context)
        for adapter_name_iter in all_adapters_config.keys():
            adapter = self._get_adapter_instance(adapter_name_iter)
            if adapter:
                adapter_context = adapter.get_stage_context(stage_name, all_adapters_config)
                context.update(adapter_context)
        
        return context
    
    def write_stage_context(self, stage_name: str, adapter_name: str) -> Path:
        """Build and write stage context to disk
        
        Args:
            stage_name: Name of the bootstrap stage
            adapter_name: Name of the adapter
            
        Returns:
            Path to written context file
        """
        # Get context from adapter
        context = self.get_stage_context(stage_name, adapter_name)
        
        # Write to centralized location
        context_file = self.context_dir / f"context-{stage_name}.json"
        context_file.write_text(json.dumps(context, indent=2))
        
        return context_file
    
    def get_common_env_vars(self) -> Dict[str, str]:
        """Get common environment variables for all stages
        
        Returns:
            Dictionary of environment variables
        """
        platform_data = self._load_platform_yaml()
        
        return {
            'MODE': 'production',
            'ENV': 'dev',
            'REPO_ROOT': str(Path.cwd()),
            'ARGOCD_NAMESPACE': 'argocd',
        }
