"""Kind cluster manager for CAPI pivot bootstrap"""

import subprocess
import random
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class KindClusterConfig:
    """Configuration for Kind cluster"""
    name: str = "ztc-bootstrap"
    api_port: Optional[int] = None  # Randomized if None
    kubeconfig_path: Path = Path.home() / ".zerotouch" / "bootstrap" / "kind-kubeconfig"


class KindClusterManager:
    """Manages ephemeral Kind clusters for CAPI pivot"""
    
    def __init__(self, config: Optional[KindClusterConfig] = None):
        """Initialize Kind cluster manager
        
        Args:
            config: Kind cluster configuration
        """
        self.config = config or KindClusterConfig()
        
    def _randomize_api_port(self) -> int:
        """Generate randomized API server port to prevent CI collisions
        
        Returns:
            Random port between 30000-32767 (NodePort range)
        """
        return random.randint(30000, 32767)
    
    def create_cluster(self) -> Path:
        """Create Kind cluster with randomized API port
        
        Returns:
            Path to kubeconfig file
            
        Raises:
            RuntimeError: If cluster creation fails
        """
        # Randomize API port if not specified
        api_port = self.config.api_port or self._randomize_api_port()
        
        # Ensure kubeconfig directory exists
        self.config.kubeconfig_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Generate Kind config with custom API port
        kind_config = f"""kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  apiServerPort: {api_port}
"""
        
        # Write Kind config to temp file
        config_file = Path("/tmp/kind-config.yaml")
        config_file.write_text(kind_config)
        
        try:
            # Create Kind cluster
            subprocess.run(
                [
                    "kind", "create", "cluster",
                    "--name", self.config.name,
                    "--config", str(config_file),
                    "--kubeconfig", str(self.config.kubeconfig_path)
                ],
                check=True,
                capture_output=True,
                text=True
            )
            
            return self.config.kubeconfig_path
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to create Kind cluster: {e.stderr}"
            ) from e
        finally:
            # Cleanup temp config
            if config_file.exists():
                config_file.unlink()
    
    def delete_cluster(self, max_retries: int = 3) -> bool:
        """Delete Kind cluster with exponential backoff retry
        
        Args:
            max_retries: Maximum number of deletion attempts
            
        Returns:
            True if deletion succeeded, False otherwise
        """
        for attempt in range(max_retries):
            try:
                subprocess.run(
                    ["kind", "delete", "cluster", "--name", self.config.name],
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                # Cleanup kubeconfig file
                if self.config.kubeconfig_path.exists():
                    self.config.kubeconfig_path.unlink()
                
                return True
                
            except subprocess.CalledProcessError as e:
                if attempt < max_retries - 1:
                    # Exponential backoff: 2^attempt seconds
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                else:
                    # Final attempt failed
                    return False
        
        return False
    
    def cluster_exists(self) -> bool:
        """Check if Kind cluster exists
        
        Returns:
            True if cluster exists, False otherwise
        """
        try:
            result = subprocess.run(
                ["kind", "get", "clusters"],
                check=True,
                capture_output=True,
                text=True
            )
            
            clusters = result.stdout.strip().split("\n")
            return self.config.name in clusters
            
        except subprocess.CalledProcessError:
            return False
    
    def get_kubeconfig_path(self) -> Path:
        """Get path to Kind cluster kubeconfig
        
        Returns:
            Path to kubeconfig file
        """
        return self.config.kubeconfig_path
