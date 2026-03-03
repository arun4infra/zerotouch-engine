"""Bootstrap prerequisite checker for CAPI pivot workflow."""

import subprocess
import shutil
import os
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PrerequisiteCheckResult:
    """Result from a single prerequisite check."""
    name: str
    success: bool
    error: Optional[str] = None


class BootstrapPrerequisiteChecker:
    """Validates prerequisites before CAPI pivot bootstrap."""
    
    def __init__(self, platform_yaml_path: Path = Path('platform/platform.yaml')):
        """Initialize checker with platform config path
        
        Args:
            platform_yaml_path: Path to platform.yaml for secrets access
        """
        self.platform_yaml_path = platform_yaml_path
    
    def check_all(self) -> Tuple[bool, List[PrerequisiteCheckResult]]:
        """Run all prerequisite checks.
        
        Returns:
            Tuple of (all_passed, list of results)
        """
        results = [
            self.check_docker_installed(),
            self.check_docker_running(),
            self.check_docker_socket_access(),
            self.check_docker_resources(),
            self.check_kubectl_installed(),
            self.check_kind_installed(),
            self.check_hetzner_token(),
            self.check_github_credentials(),
        ]
        
        all_passed = all(r.success for r in results)
        return all_passed, results
    
    def check_docker_installed(self) -> PrerequisiteCheckResult:
        """Check if Docker is installed."""
        if shutil.which("docker") is None:
            return PrerequisiteCheckResult(
                name="Docker installed",
                success=False,
                error="Docker binary not found in PATH"
            )
        return PrerequisiteCheckResult(name="Docker installed", success=True)
    
    def check_docker_running(self) -> PrerequisiteCheckResult:
        """Check if Docker daemon is running."""
        try:
            subprocess.run(
                ["docker", "info"],
                capture_output=True,
                check=True,
                timeout=5
            )
            return PrerequisiteCheckResult(name="Docker running", success=True)
        except subprocess.CalledProcessError as e:
            return PrerequisiteCheckResult(
                name="Docker running",
                success=False,
                error=f"Docker daemon not running: {e.stderr.decode()}"
            )
        except subprocess.TimeoutExpired:
            return PrerequisiteCheckResult(
                name="Docker running",
                success=False,
                error="Docker info command timed out"
            )
        except FileNotFoundError:
            return PrerequisiteCheckResult(
                name="Docker running",
                success=False,
                error="Docker binary not found"
            )
    
    def check_docker_socket_access(self) -> PrerequisiteCheckResult:
        """Check if Docker socket is accessible."""
        try:
            subprocess.run(
                ["docker", "ps"],
                capture_output=True,
                check=True,
                timeout=5
            )
            return PrerequisiteCheckResult(name="Docker socket access", success=True)
        except subprocess.CalledProcessError as e:
            return PrerequisiteCheckResult(
                name="Docker socket access",
                success=False,
                error=f"Cannot access Docker socket: {e.stderr.decode()}"
            )
        except subprocess.TimeoutExpired:
            return PrerequisiteCheckResult(
                name="Docker socket access",
                success=False,
                error="Docker ps command timed out"
            )
    
    def check_docker_resources(self) -> PrerequisiteCheckResult:
        """Check if Docker has sufficient resources (4GB RAM, 2 CPU, 20GB disk)."""
        try:
            result = subprocess.run(
                ["docker", "info", "--format", "{{json .}}"],
                capture_output=True,
                check=True,
                timeout=5
            )
            
            import json
            info = json.loads(result.stdout.decode())
            
            mem_total = info.get("MemTotal", 0)
            min_mem = 4 * 1024 * 1024 * 1024
            if mem_total < min_mem:
                return PrerequisiteCheckResult(
                    name="Docker resources",
                    success=False,
                    error=f"Insufficient memory: {mem_total / (1024**3):.1f}GB available, 4GB required"
                )
            
            ncpu = info.get("NCPU", 0)
            if ncpu < 2:
                return PrerequisiteCheckResult(
                    name="Docker resources",
                    success=False,
                    error=f"Insufficient CPUs: {ncpu} available, 2 required"
                )
            
            docker_root = info.get("DockerRootDir", "/var/lib/docker")
            check_path = docker_root if os.path.exists(docker_root) else "/"
            
            df_result = subprocess.run(
                ["df", "-k", check_path],
                capture_output=True,
                check=True,
                timeout=5
            )
            
            lines = df_result.stdout.decode().strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 4:
                    available_kb = int(parts[3])
                    available_bytes = available_kb * 1024
                    min_disk = 20 * 1024 * 1024 * 1024
                    if available_bytes < min_disk:
                        return PrerequisiteCheckResult(
                            name="Docker resources",
                            success=False,
                            error=f"Insufficient disk space: {available_bytes / (1024**3):.1f}GB available, 20GB required"
                        )
            
            return PrerequisiteCheckResult(name="Docker resources", success=True)
            
        except subprocess.CalledProcessError as e:
            return PrerequisiteCheckResult(
                name="Docker resources",
                success=False,
                error=f"Failed to check Docker resources: {e.stderr.decode()}"
            )
        except subprocess.TimeoutExpired:
            return PrerequisiteCheckResult(
                name="Docker resources",
                success=False,
                error="Docker resource check timed out"
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            return PrerequisiteCheckResult(
                name="Docker resources",
                success=False,
                error=f"Failed to parse Docker info: {str(e)}"
            )
    
    def check_kubectl_installed(self) -> PrerequisiteCheckResult:
        """Check if kubectl is installed."""
        if shutil.which("kubectl") is None:
            return PrerequisiteCheckResult(
                name="kubectl installed",
                success=False,
                error="kubectl binary not found in PATH"
            )
        return PrerequisiteCheckResult(name="kubectl installed", success=True)
    
    def check_kind_installed(self) -> PrerequisiteCheckResult:
        """Check if kind is installed."""
        if shutil.which("kind") is None:
            return PrerequisiteCheckResult(
                name="kind installed",
                success=False,
                error="kind binary not found in PATH"
            )
        return PrerequisiteCheckResult(name="kind installed", success=True)
    
    def check_hetzner_token(self) -> PrerequisiteCheckResult:
        """Check if Hetzner API token is available via secrets provider."""
        try:
            from workflow_engine.services.secrets_provider import SecretsProvider
            
            secrets_provider = SecretsProvider()
            env_vars = secrets_provider.get_env_vars(self.platform_yaml_path)
            
            token = env_vars.get("HETZNER_API_TOKEN")
            if not token:
                return PrerequisiteCheckResult(
                    name="Hetzner API token",
                    success=False,
                    error="Hetzner API token not available in decrypted secrets (hcloud secret)"
                )
            return PrerequisiteCheckResult(name="Hetzner API token", success=True)
        except Exception as e:
            return PrerequisiteCheckResult(
                name="Hetzner API token",
                success=False,
                error=f"Failed to access secrets: {str(e)}"
            )
    
    def check_github_credentials(self) -> PrerequisiteCheckResult:
        """Check if GitHub credentials are available via secrets provider."""
        try:
            from workflow_engine.services.secrets_provider import SecretsProvider
            
            secrets_provider = SecretsProvider()
            env_vars = secrets_provider.get_env_vars(self.platform_yaml_path)
            
            git_app_key = env_vars.get("GIT_APP_PRIVATE_KEY")
            git_app_id = env_vars.get("GIT_APP_ID")
            
            if not git_app_key or not git_app_id:
                return PrerequisiteCheckResult(
                    name="GitHub credentials",
                    success=False,
                    error="GitHub App credentials not available in decrypted secrets (github-app-credentials secret)"
                )
            return PrerequisiteCheckResult(name="GitHub credentials", success=True)
        except Exception as e:
            return PrerequisiteCheckResult(
                name="GitHub credentials",
                success=False,
                error=f"Failed to access secrets: {str(e)}"
            )
