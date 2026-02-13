"""Adapter registry for discovery and loading"""

from typing import Dict, List, Optional
from pathlib import Path
import importlib
import yaml


class AdapterRegistry:
    """Registry for adapter discovery and loading"""
    
    def __init__(self, auto_discover: bool = True):
        self._adapter_classes: Dict[str, type] = {}
        self._metadata: Dict[str, Dict] = {}
        
        # Auto-discover adapters by default
        if auto_discover:
            self.discover_adapters()
    
    def register(self, adapter_class: type):
        """Register an adapter class"""
        # Instantiate temporarily to get metadata
        temp_instance = adapter_class({})
        metadata = temp_instance.load_metadata()
        
        adapter_name = metadata["name"]
        self._adapter_classes[adapter_name] = adapter_class
        self._metadata[adapter_name] = metadata
    
    def get_adapter(self, name: str, config: Dict = None):
        """Get adapter instance by name
        
        Args:
            name: Adapter name
            config: Configuration dict for adapter (optional, defaults to empty dict)
            
        Returns:
            Instantiated adapter
        """
        if name not in self._adapter_classes:
            raise KeyError(f"Adapter '{name}' not found in registry")
        
        if config is None:
            config = {}
        
        return self._adapter_classes[name](config)
    
    def list_adapters(self) -> List[str]:
        """List all registered adapter names"""
        return list(self._adapter_classes.keys())
    
    def get_metadata(self, name: str) -> Dict:
        """Get adapter metadata by name"""
        if name not in self._metadata:
            raise KeyError(f"Adapter '{name}' not found in registry")
        return self._metadata[name]
    
    def discover_adapters(self, adapters_path: Optional[Path] = None):
        """Discover and register adapters from adapters directory"""
        if adapters_path is None:
            adapters_path = Path(__file__).parent.parent / "adapters"
        
        for adapter_dir in adapters_path.iterdir():
            if not adapter_dir.is_dir() or adapter_dir.name.startswith("_"):
                continue
            
            adapter_module_path = f"ztc.adapters.{adapter_dir.name}.adapter"
            try:
                module = importlib.import_module(adapter_module_path)
                # Look for adapter class (convention: {Name}Adapter)
                adapter_class_name = f"{adapter_dir.name.capitalize()}Adapter"
                if hasattr(module, adapter_class_name):
                    adapter_class = getattr(module, adapter_class_name)
                    self.register(adapter_class)
            except (ImportError, AttributeError):
                # Skip if adapter module doesn't exist or doesn't follow convention
                pass
