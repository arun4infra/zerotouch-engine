"""Version provider service - centralized version management"""

from pathlib import Path
from typing import Optional, Dict, Any
import yaml


class VersionProvider:
    """Provides version information from platform.yaml and versions.yaml
    
    Version resolution order:
    1. platform.yaml adapter config (user overrides)
    2. versions.yaml defaults (version matrix)
    3. None (adapter must handle missing version)
    """
    
    def __init__(self, platform_yaml_path: Path = Path("platform/platform.yaml")):
        """Initialize version provider
        
        Args:
            platform_yaml_path: Path to platform.yaml file
        """
        self.platform_yaml_path = platform_yaml_path
        self._platform_cache: Optional[Dict[str, Any]] = None
        self._versions_cache: Optional[Dict[str, Any]] = None
    
    def _load_platform_yaml(self) -> Dict[str, Any]:
        """Load and cache platform.yaml"""
        if self._platform_cache is None:
            if not self.platform_yaml_path.exists():
                self._platform_cache = {}
            else:
                with open(self.platform_yaml_path) as f:
                    self._platform_cache = yaml.safe_load(f) or {}
        return self._platform_cache
    
    def _load_versions_yaml(self) -> Dict[str, Any]:
        """Load and cache versions.yaml"""
        if self._versions_cache is None:
            # Determine version matrix to use (default: 1.0)
            platform_data = self._load_platform_yaml()
            version_matrix = platform_data.get('platform', {}).get('version_matrix', '1.0')
            
            versions_path = Path(__file__).parent.parent / f"templates/versions/{version_matrix}/versions.yaml"
            if not versions_path.exists():
                self._versions_cache = {}
            else:
                with open(versions_path) as f:
                    self._versions_cache = yaml.safe_load(f) or {}
        return self._versions_cache
    
    def get_version(self, adapter_name: str, field_name: str) -> Optional[Any]:
        """Get version configuration for an adapter
        
        Resolution order:
        1. platform.yaml: adapters.<adapter_name>.<field_name>
        2. versions.yaml: adapters.<adapter_name>.<field_name>
        3. None
        
        Args:
            adapter_name: Name of the adapter (e.g., 'cilium', 'argocd')
            field_name: Field name (e.g., 'version', 'default_envoy_image')
        
        Returns:
            Version value, or None if not found
        
        Example:
            provider = VersionProvider()
            cilium_version = provider.get_version('cilium', 'version')
            envoy_image = provider.get_version('cilium', 'default_envoy_image')
        """
        # 1. Check platform.yaml (user overrides)
        platform_data = self._load_platform_yaml()
        adapters_config = platform_data.get('adapters', {})
        adapter_config = adapters_config.get(adapter_name, {})
        
        if field_name in adapter_config:
            return adapter_config[field_name]
        
        # 2. Check versions.yaml (defaults)
        versions_data = self._load_versions_yaml()
        versions_adapters = versions_data.get('adapters', {})
        versions_adapter = versions_adapters.get(adapter_name, {})
        
        return versions_adapter.get(field_name)
    
    def get_all_versions(self, adapter_name: str) -> Dict[str, Any]:
        """Get all version configuration for an adapter
        
        Merges versions.yaml defaults with platform.yaml overrides.
        
        Args:
            adapter_name: Name of the adapter
        
        Returns:
            Dictionary of all version fields for the adapter
        """
        # Start with versions.yaml defaults
        versions_data = self._load_versions_yaml()
        versions_adapters = versions_data.get('adapters', {})
        result = versions_adapters.get(adapter_name, {}).copy()
        
        # Override with platform.yaml values
        platform_data = self._load_platform_yaml()
        adapters_config = platform_data.get('adapters', {})
        adapter_config = adapters_config.get(adapter_name, {})
        result.update(adapter_config)
        
        return result
    
    def clear_cache(self) -> None:
        """Clear cached data (useful for testing or reloading)"""
        self._platform_cache = None
        self._versions_cache = None
