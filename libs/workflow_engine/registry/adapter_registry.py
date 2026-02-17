"""Adapter registry for discovery and loading"""

from typing import Dict, List, Optional
from pathlib import Path
import importlib


class AdapterRegistry:
    """Registry for adapter discovery and loading"""
    
    def __init__(self, auto_discover: bool = True):
        self._adapter_classes: Dict[str, type] = {}
        self._metadata: Dict[str, Dict] = {}
        if auto_discover:
            self.discover_adapters()
    
    def register(self, adapter_class: type):
        temp_instance = adapter_class({})
        metadata = temp_instance.load_metadata()
        adapter_name = metadata["name"]
        self._adapter_classes[adapter_name] = adapter_class
        self._metadata[adapter_name] = metadata
    
    def get_adapter_class(self, name: str) -> type:
        if name not in self._adapter_classes:
            raise KeyError(f"Adapter '{name}' not found in registry")
        return self._adapter_classes[name]
    
    def get_adapter(self, name: str, config: Dict = None):
        if name not in self._adapter_classes:
            raise KeyError(f"Adapter '{name}' not found in registry")
        if config is None:
            config = {}
        return self._adapter_classes[name](config)
    
    def list_adapters(self) -> List[str]:
        return list(self._adapter_classes.keys())
    
    def get_metadata(self, name: str) -> Dict:
        if name not in self._metadata:
            raise KeyError(f"Adapter '{name}' not found in registry")
        return self._metadata[name]
    
    def discover_adapters(self, adapters_path: Optional[Path] = None):
        if adapters_path is None:
            adapters_path = Path(__file__).parent.parent / "adapters"
        for adapter_dir in adapters_path.iterdir():
            if not adapter_dir.is_dir() or adapter_dir.name.startswith("_"):
                continue
            adapter_module_path = f"workflow_engine.adapters.{adapter_dir.name}.adapter"
            try:
                module = importlib.import_module(adapter_module_path)
                clean_name = adapter_dir.name.replace("-", "").replace("_", "")
                possible_names = [
                    f"{adapter_dir.name.capitalize()}Adapter",
                    f"{adapter_dir.name.upper()}Adapter",
                    f"{adapter_dir.name.title()}Adapter",
                    f"{clean_name.title()}Adapter"
                ]
                if "-" in adapter_dir.name or "_" in adapter_dir.name:
                    parts = adapter_dir.name.replace("_", "-").split("-")
                    camel_case = "".join(p.capitalize() for p in parts)
                    possible_names.append(f"{camel_case}Adapter")
                for adapter_class_name in possible_names:
                    if hasattr(module, adapter_class_name):
                        adapter_class = getattr(module, adapter_class_name)
                        self.register(adapter_class)
                        break
            except (ImportError, AttributeError):
                pass
