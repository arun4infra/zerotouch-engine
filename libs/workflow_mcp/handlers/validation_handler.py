"""Validation handler for MCP tools"""

import json
from pathlib import Path


class ValidationHandler:
    def __init__(self, mcp, allow_write: bool = False):
        self.mcp = mcp
        self.allow_write = allow_write
        self._register_tools()
    
    def _register_tools(self):
        @self.mcp.tool()
        async def validate_artifacts(platform_yaml_path: str) -> str:
            """Validate generated artifacts against lock file"""
            try:
                from workflow_engine.engine import PlatformEngine
                lock_file = Path("platform/lock.json")
                if not lock_file.exists():
                    return json.dumps({"valid": False, "error": "Lock file not found"})
                
                with open(lock_file, 'r') as f:
                    lock_data = json.load(f)
                
                engine = PlatformEngine(Path(platform_yaml_path))
                platform_hash = engine.hash_file(Path(platform_yaml_path))
                artifacts_hash = engine.hash_directory(Path("platform/generated"))
                
                if platform_hash != lock_data.get("platform_hash"):
                    return json.dumps({"valid": False, "error": "Platform configuration has changed"})
                if artifacts_hash != lock_data.get("artifacts_hash"):
                    return json.dumps({"valid": False, "error": "Artifacts have been modified"})
                
                return json.dumps({"valid": True, "message": "Artifacts match lock file"})
            except Exception as e:
                return json.dumps({"valid": False, "error": str(e)})
        
        @self.mcp.tool()
        async def validate_runtime_dependencies() -> str:
            """Validate runtime dependencies (kubectl, talosctl, etc.)"""
            import shutil
            dependencies = {
                "kubectl": shutil.which("kubectl") is not None,
                "talosctl": shutil.which("talosctl") is not None,
                "jq": shutil.which("jq") is not None,
                "yq": shutil.which("yq") is not None
            }
            all_present = all(dependencies.values())
            return json.dumps({
                "valid": all_present,
                "dependencies": dependencies,
                "missing": [k for k, v in dependencies.items() if not v]
            })
        
        @self.mcp.tool()
        async def validate_cluster_access(kubeconfig_path: str = None) -> str:
            """Validate cluster access via kubectl"""
            import subprocess
            try:
                cmd = ["kubectl", "cluster-info"]
                if kubeconfig_path:
                    cmd.extend(["--kubeconfig", kubeconfig_path])
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    return json.dumps({"accessible": True, "output": result.stdout})
                return json.dumps({"accessible": False, "error": result.stderr})
            except Exception as e:
                return json.dumps({"accessible": False, "error": str(e)})
