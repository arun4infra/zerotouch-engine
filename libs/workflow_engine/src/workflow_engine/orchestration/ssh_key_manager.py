"""SSH Key Manager for CAPI clusters

Manages SSH key lifecycle for Cluster API Provider Hetzner (CAPH).
SSH keys must be uploaded to Hetzner Cloud before CAPH can provision VMs.
"""

import subprocess
import requests
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class SSHKeyConfig:
    """SSH key configuration"""
    cluster_name: str
    key_path: Path = Path.home() / ".ssh" / "id_ed25519"
    hcloud_token: Optional[str] = None


class SSHKeyManager:
    """Manages SSH keys for CAPI clusters"""
    
    def __init__(self, config: SSHKeyConfig):
        self.config = config
        self.key_name = f"{config.cluster_name}-capi-key"
    
    def ensure_ssh_key_exists(self) -> str:
        """Ensure SSH key exists locally, create if missing
        
        Returns:
            Path to public key file
        """
        if not self.config.key_path.exists():
            # Generate new SSH key pair
            subprocess.run(
                [
                    "ssh-keygen",
                    "-t", "ed25519",
                    "-f", str(self.config.key_path),
                    "-N", "",  # No passphrase
                    "-C", f"{self.config.cluster_name}-capi"
                ],
                check=True,
                capture_output=True
            )
        
        pub_key_path = Path(str(self.config.key_path) + ".pub")
        if not pub_key_path.exists():
            raise FileNotFoundError(f"Public key not found: {pub_key_path}")
        
        return str(pub_key_path)
    
    def upload_to_hetzner(self) -> str:
        """Upload SSH key to Hetzner Cloud
        
        Returns:
            SSH key name in Hetzner Cloud
            
        Raises:
            RuntimeError: If upload fails
        """
        if not self.config.hcloud_token:
            raise ValueError("HCLOUD_TOKEN required to upload SSH key")
        
        pub_key_path = self.ensure_ssh_key_exists()
        pub_key_content = Path(pub_key_path).read_text().strip()
        
        # Check if key already exists
        response = requests.get(
            "https://api.hetzner.cloud/v1/ssh_keys",
            headers={"Authorization": f"Bearer {self.config.hcloud_token}"}
        )
        response.raise_for_status()
        
        for key in response.json().get("ssh_keys", []):
            if key["name"] == self.key_name:
                return self.key_name
        
        # Upload new key
        response = requests.post(
            "https://api.hetzner.cloud/v1/ssh_keys",
            headers={"Authorization": f"Bearer {self.config.hcloud_token}"},
            json={
                "name": self.key_name,
                "public_key": pub_key_content
            }
        )
        response.raise_for_status()
        
        return self.key_name
    
    def delete_from_hetzner(self) -> None:
        """Delete SSH key from Hetzner Cloud"""
        if not self.config.hcloud_token:
            return
        
        # Get key ID by name
        response = requests.get(
            "https://api.hetzner.cloud/v1/ssh_keys",
            headers={"Authorization": f"Bearer {self.config.hcloud_token}"}
        )
        
        if response.status_code != 200:
            return
        
        for key in response.json().get("ssh_keys", []):
            if key["name"] == self.key_name:
                # Delete key
                requests.delete(
                    f"https://api.hetzner.cloud/v1/ssh_keys/{key['id']}",
                    headers={"Authorization": f"Bearer {self.config.hcloud_token}"}
                )
                break
