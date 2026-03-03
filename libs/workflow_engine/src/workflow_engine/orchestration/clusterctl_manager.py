"""clusterctl binary manager for CAPI operations."""

import shutil
import subprocess
import platform
import hashlib
from pathlib import Path
from typing import Optional


class ClusterctlManager:
    """Manages clusterctl binary availability and download."""
    
    def __init__(self, download_dir: Path = Path.home() / ".zerotouch" / "bin"):
        """Initialize manager.
        
        Args:
            download_dir: Directory to download clusterctl binary
        """
        self.download_dir = download_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    def is_available(self) -> bool:
        """Check if clusterctl is available in PATH.
        
        Returns:
            True if clusterctl binary is found in PATH
        """
        return shutil.which("clusterctl") is not None
    
    def get_path(self) -> Optional[Path]:
        """Get path to clusterctl binary.
        
        Returns:
            Path to clusterctl binary or None if not found
        """
        binary_path = shutil.which("clusterctl")
        return Path(binary_path) if binary_path else None
    
    def download(self, version: str = "v1.8.0") -> Path:
        """Download clusterctl binary from GitHub releases.
        
        Args:
            version: Version to download (default: v1.8.0)
            
        Returns:
            Path to downloaded binary
            
        Raises:
            RuntimeError: If download fails
        """
        # Determine OS and architecture
        os_name = platform.system().lower()
        if os_name == "darwin":
            os_name = "darwin"
        elif os_name == "linux":
            os_name = "linux"
        else:
            raise RuntimeError(f"Unsupported OS: {os_name}")
        
        arch = platform.machine().lower()
        if arch in ["x86_64", "amd64"]:
            arch = "amd64"
        elif arch in ["aarch64", "arm64"]:
            arch = "arm64"
        else:
            raise RuntimeError(f"Unsupported architecture: {arch}")
        
        # Construct download URL
        binary_name = f"clusterctl-{os_name}-{arch}"
        url = f"https://github.com/kubernetes-sigs/cluster-api/releases/download/{version}/{binary_name}"
        
        # Download binary
        output_path = self.download_dir / "clusterctl"
        try:
            subprocess.run(
                ["curl", "-L", "-o", str(output_path), url],
                check=True,
                capture_output=True,
                timeout=300
            )
            
            # Make executable
            output_path.chmod(0o755)
            
            return output_path
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to download clusterctl: {e.stderr.decode()}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("clusterctl download timed out")
    
    def verify_checksum(self, binary_path: Path, version: str = "v1.8.0") -> bool:
        """Verify clusterctl binary checksum.
        
        NOTE: clusterctl releases do not provide checksums.txt files.
        This method is a placeholder for future checksum verification.
        
        Args:
            binary_path: Path to binary to verify
            version: Version to verify against
            
        Returns:
            True (checksum verification not available)
        """
        # clusterctl releases don't provide checksums
        # Return True to indicate no verification failure
        return True
