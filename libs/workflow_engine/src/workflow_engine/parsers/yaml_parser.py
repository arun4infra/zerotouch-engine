"""Parser for YAML files."""

from pathlib import Path
from typing import Dict, Any
import yaml


class YAMLParser:
    """Parser for YAML files using PyYAML with safe_load."""

    def load(self, file_path: Path) -> Dict[str, Any]:
        """Load YAML file.
        
        Args:
            file_path: Path to YAML file
            
        Returns:
            Dictionary containing parsed YAML data, or empty dict if file is empty
        """
        with open(file_path) as f:
            return yaml.safe_load(f) or {}

    def save(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Save YAML file.
        
        Args:
            file_path: Path to YAML file
            data: Dictionary to save as YAML
        """
        with open(file_path, 'w') as f:
            yaml.dump(data, f, sort_keys=False, default_flow_style=False, indent=2)
