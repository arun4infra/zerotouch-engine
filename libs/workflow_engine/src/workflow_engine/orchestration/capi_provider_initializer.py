"""CAPI provider initializer for bootstrap workflow"""

import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class CAPIProviderConfig:
    """Configuration for CAPI provider initialization"""
    kubeconfig_path: Path
    hetzner_token: str
    clusterctl_path: Optional[Path] = None
    infrastructure_provider: str = "hetzner:v1.0.7"
    bootstrap_provider: str = "talos"
    control_plane_provider: str = "talos"


class CAPIProviderInitializer:
    """Initializes CAPI providers on Kind cluster"""
    
    def __init__(self, config: CAPIProviderConfig):
        """Initialize CAPI provider initializer
        
        Args:
            config: CAPI provider configuration
        """
        self.config = config
    
    def initialize_providers(self) -> bool:
        """Initialize CAPI providers using clusterctl init
        
        Returns:
            True if initialization succeeded
            
        Raises:
            RuntimeError: If initialization fails
        """
        try:
            # Inherit current environment and add CAPI-specific vars
            import os
            env = os.environ.copy()
            env["KUBECONFIG"] = str(self.config.kubeconfig_path)
            env["HCLOUD_TOKEN"] = self.config.hetzner_token
            
            # Use provided clusterctl path or default to PATH
            clusterctl_cmd = str(self.config.clusterctl_path) if self.config.clusterctl_path else "clusterctl"
            
            # Run clusterctl init
            subprocess.run(
                [
                    clusterctl_cmd, "init",
                    "--infrastructure", self.config.infrastructure_provider,
                    "--bootstrap", self.config.bootstrap_provider,
                    "--control-plane", self.config.control_plane_provider
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env
            )
            
            return True
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to initialize CAPI providers: {e.stderr}"
            ) from e
    
    def apply_capi_manifests(self, manifests_dir: Path) -> bool:
        """Apply CAPI manifests to Kind cluster
        
        Args:
            manifests_dir: Directory containing CAPI manifests
            
        Returns:
            True if application succeeded
            
        Raises:
            RuntimeError: If application fails
        """
        try:
            # Apply all YAML files in manifests directory
            subprocess.run(
                [
                    "kubectl", "apply",
                    "-f", str(manifests_dir),
                    "--kubeconfig", str(self.config.kubeconfig_path)
                ],
                check=True,
                capture_output=True,
                text=True
            )
            
            return True
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to apply CAPI manifests: {e.stderr}"
            ) from e
