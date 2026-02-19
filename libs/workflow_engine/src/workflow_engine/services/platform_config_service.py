"""Service for platform.yaml management."""

from pathlib import Path
from typing import Dict, Any, Optional

from ..models.platform_config import PlatformConfig, PlatformInfo
from ..parsers.yaml_parser import YAMLParser


class PlatformConfigService:
    """Service for platform.yaml management.
    
    Provides methods for reading, writing, and incrementally updating
    platform configuration stored in platform.yaml.
    """

    def __init__(self, config_path: Path = Path("platform/platform.yaml")):
        """Initialize service with config path.
        
        Args:
            config_path: Path to platform.yaml file (default: platform/platform.yaml)
        """
        self.config_path = config_path
        self.yaml_parser = YAMLParser()

    def exists(self) -> bool:
        """Check if platform.yaml exists.
        
        Returns:
            True if platform.yaml exists, False otherwise
        """
        return self.config_path.exists()

    def load(self) -> PlatformConfig:
        """Load platform configuration.
        
        Returns:
            PlatformConfig object with parsed configuration
            
        Raises:
            FileNotFoundError: If platform.yaml does not exist
        """
        if not self.exists():
            raise FileNotFoundError(f"Platform config not found: {self.config_path}")

        data = self.yaml_parser.load(self.config_path)
        return PlatformConfig(**data)

    def save(self, config: PlatformConfig) -> None:
        """Save platform configuration.
        
        Creates parent directories if they don't exist.
        
        Args:
            config: PlatformConfig object to save
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.yaml_parser.save(self.config_path, config.model_dump())

    def save_adapter(self, adapter_name: str, adapter_config: Dict[str, Any]) -> None:
        """Incrementally save adapter config.
        
        If platform.yaml exists, loads it and updates the adapter config.
        If it doesn't exist, creates a new minimal config with the adapter.
        
        Args:
            adapter_name: Name of the adapter (e.g., "aws", "github")
            adapter_config: Configuration dictionary for the adapter
        """
        if self.exists():
            config = self.load()
        else:
            config = PlatformConfig(
                version="1.0",
                platform=PlatformInfo(organization="", app_name=""),
                adapters={}
            )

        config.adapters[adapter_name] = adapter_config
        self.save(config)

    def load_adapters(self) -> Dict[str, Dict[str, Any]]:
        """Load only adapter configs for cross-adapter access.
        
        Returns:
            Dictionary of adapter configurations keyed by adapter name.
            Returns empty dict if platform.yaml doesn't exist.
        """
        if not self.exists():
            return {}

        config = self.load()
        return config.adapters
