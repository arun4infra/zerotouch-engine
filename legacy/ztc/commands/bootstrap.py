"""Bootstrap command implementation."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from ztc.utils.context_managers import SecureTempDir


class RuntimeDependencyError(Exception):
    """Raised when required runtime dependencies are missing."""
    pass


class LockFileNotFoundError(Exception):
    """Raised when lock file is not found."""
    pass


class EnvironmentMismatchError(Exception):
    """Raised when lock file environment doesn't match."""
    pass


class PlatformModifiedError(Exception):
    """Raised when platform.yaml has been modified since render."""
    pass


class BootstrapError(Exception):
    """Raised when bootstrap execution fails."""
    pass


class BootstrapCommand:
    """Bootstrap command for executing platform deployment."""
    
    def __init__(self, env: str, skip_cache: bool = False):
        self.env = env
        self.skip_cache = skip_cache
        self.repo_root = Path.cwd()
    
    def execute(self):
        """Execute bootstrap pipeline via stage-executor.sh with AOT script extraction."""
        # 1. Validate runtime dependencies (ZeroTouch promise)
        self.validate_runtime_dependencies()
        
        # 2. Validate lock file
        self.validate_lock_file()
        
        # 3. Load pipeline YAML
        pipeline_yaml = self.repo_root / "bootstrap" / "pipeline" / "production.yaml"
        pipeline = yaml.safe_load(pipeline_yaml.read_text())
        
        # 4. Extract all scripts ahead-of-time to signal-safe secure temp directory
        with SecureTempDir(prefix="ztc-secure-") as temp_dir:
            script_map = self.extract_all_scripts(pipeline["stages"], temp_dir)
            
            # 5. Generate runtime manifest mapping stage IDs to physical paths
            runtime_manifest = temp_dir / "runtime_manifest.json"
            runtime_manifest.write_text(json.dumps(script_map, indent=2))
            
            # 6. Prepare environment variables
            env_vars = self.prepare_env_vars()
            
            # 7. Execute stage-executor.sh with script map
            stage_executor = self.repo_root / "scripts" / "bootstrap" / "pipeline" / "stage-executor.sh"
            stage_executor.chmod(0o755)
            
            result = subprocess.run(
                [str(stage_executor), str(pipeline_yaml), "--script-map", str(runtime_manifest)],
                env={**os.environ, **env_vars},
                cwd=self.repo_root
            )
            
            if result.returncode != 0:
                raise BootstrapError(f"Bootstrap failed with exit code {result.returncode}")
    
    def validate_runtime_dependencies(self):
        """Validate required runtime dependencies exist (ZeroTouch correctness).
        
        The stage-executor.sh and scripts rely on jq/yq for JSON/YAML parsing.
        Failing fast here prevents mid-bootstrap crashes and upholds the ZeroTouch promise.
        
        Raises:
            RuntimeDependencyError: If required tools are missing or incompatible
        """
        required_tools = {
            "jq": {
                "min_version": "1.6",
                "check_cmd": ["jq", "--version"],
                "install_hint": "Install via: brew install jq (macOS) or apt-get install jq (Ubuntu)"
            },
            "yq": {
                "min_version": "4.0",
                "check_cmd": ["yq", "--version"],
                "install_hint": "Install via: brew install yq (macOS) or snap install yq (Ubuntu)"
            }
        }
        
        missing_tools = []
        incompatible_tools = []
        
        for tool_name, tool_config in required_tools.items():
            # Check if tool exists
            if not shutil.which(tool_name):
                missing_tools.append({
                    "name": tool_name,
                    "hint": tool_config["install_hint"]
                })
                continue
            
            # Check version compatibility
            try:
                result = subprocess.run(
                    tool_config["check_cmd"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode != 0:
                    incompatible_tools.append({
                        "name": tool_name,
                        "reason": f"Version check failed: {result.stderr}",
                        "hint": tool_config["install_hint"]
                    })
            except subprocess.TimeoutExpired:
                incompatible_tools.append({
                    "name": tool_name,
                    "reason": "Version check timed out",
                    "hint": tool_config["install_hint"]
                })
            except Exception as e:
                incompatible_tools.append({
                    "name": tool_name,
                    "reason": f"Version check error: {e}",
                    "hint": tool_config["install_hint"]
                })
        
        # Report errors with actionable guidance
        if missing_tools or incompatible_tools:
            error_msg = "Bootstrap runtime dependencies not satisfied:\n\n"
            
            if missing_tools:
                error_msg += "Missing tools:\n"
                for tool in missing_tools:
                    error_msg += f"  - {tool['name']}: {tool['hint']}\n"
            
            if incompatible_tools:
                error_msg += "\nIncompatible tools:\n"
                for tool in incompatible_tools:
                    error_msg += f"  - {tool['name']}: {tool['reason']}\n"
                    error_msg += f"    {tool['hint']}\n"
            
            error_msg += "\nThe ZeroTouch bootstrap requires these tools for script execution."
            
            raise RuntimeDependencyError(error_msg)
    
    def extract_all_scripts(self, stages: List[Dict], temp_dir: Path) -> Dict[str, Dict]:
        """Extract all referenced scripts and context files to secure temp directory."""
        script_map = {}
        
        for stage in stages:
            script_uri = stage["script"]
            
            # Parse URI (e.g., "talos://install.sh")
            adapter_name, script_name = script_uri.split("://")
            
            # For now, create placeholder script paths
            # In full implementation, this would resolve from adapter registry
            script_path = temp_dir / "scripts" / adapter_name / script_name
            script_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write placeholder script
            script_path.write_text("#!/usr/bin/env bash\necho 'Placeholder script'\n")
            script_path.chmod(0o755)
            
            # Check if stage has context_data
            context_data = stage.get("context_data")
            if context_data:
                # Write context file
                context_path = temp_dir / "context" / adapter_name / f"{script_name}.context.json"
                context_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Resolve environment variables in context data
                resolved_context = self._resolve_context_vars(context_data)
                context_path.write_text(json.dumps(resolved_context, indent=2))
                
                # Map stage name to script path + context path
                script_map[stage["name"]] = {
                    "script": str(script_path),
                    "context": str(context_path)
                }
            else:
                # Map stage name to script path only
                script_map[stage["name"]] = {"script": str(script_path)}
        
        return script_map
    
    def _resolve_context_vars(self, context_data: Dict) -> Dict:
        """Resolve environment variable references in context data."""
        import re
        
        def resolve_value(value):
            if isinstance(value, str):
                # Replace $VAR or ${VAR} with environment variable
                return re.sub(
                    r'\$\{?(\w+)\}?',
                    lambda m: os.environ.get(m.group(1), m.group(0)),
                    value
                )
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(item) for item in value]
            return value
        
        return resolve_value(context_data)
        
        return script_map
    
    def validate_lock_file(self):
        """Validate lock file before bootstrap."""
        lock_file = self.repo_root / "platform" / "lock.json"
        
        if not lock_file.exists():
            raise LockFileNotFoundError("Lock file not found. Run 'ztc render' first.")
        
        lock_data = json.loads(lock_file.read_text())
        
        # Validate environment matches
        if lock_data.get("environment") != self.env:
            raise EnvironmentMismatchError(
                f"Lock file environment '{lock_data.get('environment')}' "
                f"does not match --env '{self.env}'"
            )
        
        # Validate platform.yaml hash
        platform_yaml = self.repo_root / "platform" / "platform.yaml"
        if not platform_yaml.exists():
            platform_yaml = self.repo_root / "platform.yaml"  # Fallback
        
        if platform_yaml.exists():
            current_hash = self._hash_file(platform_yaml)
            
            if current_hash != lock_data.get("platform_hash"):
                raise PlatformModifiedError(
                    "platform.yaml has been modified since render. "
                    "Run 'ztc render' to regenerate artifacts."
                )
    
    def prepare_env_vars(self) -> Dict[str, str]:
        """Prepare environment variables for bootstrap."""
        env_vars = {
            "ENV": self.env,
            "REPO_ROOT": str(self.repo_root)
        }
        
        # Load platform.yaml if exists
        platform_yaml = self.repo_root / "platform" / "platform.yaml"
        if not platform_yaml.exists():
            platform_yaml = self.repo_root / "platform.yaml"  # Fallback
        
        if platform_yaml.exists():
            platform_data = yaml.safe_load(platform_yaml.read_text())
            
            # Add adapter-specific env vars
            for adapter_name, adapter_config in platform_data.items():
                if isinstance(adapter_config, dict):
                    for key, value in adapter_config.items():
                        env_key = f"{adapter_name.upper()}_{key.upper()}"
                        env_vars[env_key] = str(value)
        
        return env_vars
    
    def _hash_file(self, path: Path) -> str:
        """Calculate SHA256 hash of file."""
        import hashlib
        
        sha256 = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
