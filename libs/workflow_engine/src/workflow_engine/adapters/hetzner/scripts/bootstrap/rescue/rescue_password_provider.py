"""Rescue Password Provider - Persists rescue passwords to cache and tenant repo"""

import subprocess
from pathlib import Path
from typing import Optional


class RescuePasswordProvider:
    """Handles rescue password persistence to local cache and tenant git repo"""
    
    def __init__(self, cache_dir: Path = Path(".zerotouch-cache")):
        """Initialize provider
        
        Args:
            cache_dir: Local cache directory for password storage
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.password_file = self.cache_dir / "rescue-password.txt"
    
    def save_to_cache(self, password: str) -> None:
        """Save password to local cache
        
        Args:
            password: Rescue mode root password
        """
        self.password_file.write_text(password)
        self.password_file.chmod(0o600)
    
    def get_from_cache(self) -> Optional[str]:
        """Get password from local cache
        
        Returns:
            Password string, or None if not found
        """
        if self.password_file.exists():
            return self.password_file.read_text().strip()
        return None
    
    def save_to_tenant_repo(
        self, 
        password: str,
        tenant_cache_dir: Path,
        helpers_dir: Path,
        env: str = "dev",
        cluster_name: str = "",
        controlplane_name: str = "",
        controlplane_ip: str = "",
        talos_version: str = "v1.11.5"
    ) -> bool:
        """Save password to tenant repository YAML and commit
        
        Args:
            password: Rescue mode root password
            tenant_cache_dir: Tenant repo cache directory
            helpers_dir: Path to helper scripts directory
            env: Environment name
            cluster_name: Cluster name for template
            controlplane_name: Control plane node name
            controlplane_ip: Control plane IP
            talos_version: Talos version
        
        Returns:
            True if successful, False otherwise
        """
        try:
            values_file = tenant_cache_dir / "environments" / env / "talos-values.yaml"
            
            # Initialize tenant structure if missing
            if not values_file.exists():
                print(f"Initializing tenant repository structure for {env}...")
                rescue_dir = Path(__file__).parent
                init_script = rescue_dir / "init-tenant-structure.sh"
                
                subprocess.run(
                    [
                        'bash', str(init_script),
                        str(tenant_cache_dir),
                        env,
                        password,
                        cluster_name,
                        controlplane_name,
                        controlplane_ip,
                        talos_version
                    ],
                    check=True
                )
                print(f"✓ Tenant structure initialized")
            else:
                # Update existing file
                # Check if yq is available
                result = subprocess.run(['which', 'yq'], capture_output=True)
                
                if result.returncode != 0:
                    print("WARNING: yq not installed, skipping tenant repo update")
                    return False
                
                # Update YAML with yq
                subprocess.run(
                    [
                        'yq', 'eval',
                        f'.controlplane.rescue_password = "{password}"',
                        '-i', str(values_file)
                    ],
                    check=True
                )
                
                print(f"Password updated in {values_file}")
            
            # Commit and push to tenant repo
            update_script = helpers_dir / "update-tenant-config.sh"
            if update_script.exists():
                subprocess.run(
                    [
                        'bash', str(update_script),
                        str(values_file),
                        f"Update rescue password ({env})",
                        str(tenant_cache_dir)
                    ],
                    check=True
                )
                print("Changes pushed to tenant repository")
                return True
            else:
                print(f"WARNING: {update_script} not found")
                return False
                
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to update tenant repo: {e}")
            return False
        except Exception as e:
            print(f"ERROR: Unexpected error updating tenant repo: {e}")
            return False
