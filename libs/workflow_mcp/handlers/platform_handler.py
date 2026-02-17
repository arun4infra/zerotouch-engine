"""Platform handler for MCP tools"""

import json
import yaml
from pathlib import Path


class PlatformHandler:
    def __init__(self, mcp, allow_write: bool = False):
        self.mcp = mcp
        self.allow_write = allow_write
        self._register_tools()
    
    def _register_tools(self):
        @self.mcp.tool()
        async def generate_platform_yaml(project_name: str, adapter_name: str, config: dict) -> str:
            """Generate platform.yaml content"""
            platform_data = {
                "project": project_name,
                "adapters": {
                    adapter_name: config
                }
            }
            yaml_content = yaml.dump(platform_data, sort_keys=False)
            return json.dumps({"yaml_content": yaml_content})
        
        @self.mcp.tool()
        async def validate_platform_yaml(yaml_path: str) -> str:
            """Validate platform.yaml structure"""
            try:
                with open(yaml_path, 'r') as f:
                    data = yaml.safe_load(f)
                if not isinstance(data, dict):
                    return json.dumps({"valid": False, "error": "Invalid YAML structure"})
                if "adapters" not in data:
                    return json.dumps({"valid": False, "error": "Missing 'adapters' key"})
                return json.dumps({"valid": True})
            except Exception as e:
                return json.dumps({"valid": False, "error": str(e)})
        
        @self.mcp.tool()
        async def get_platform_status(platform_yaml_path: str) -> str:
            """Get platform deployment status"""
            lock_file = Path("platform/lock.json")
            if not lock_file.exists():
                return json.dumps({"status": "not_rendered", "message": "No lock file found"})
            try:
                with open(lock_file, 'r') as f:
                    lock_data = json.load(f)
                return json.dumps({"status": "rendered", "lock_data": lock_data})
            except Exception as e:
                return json.dumps({"status": "error", "error": str(e)})
        
        @self.mcp.tool()
        async def merge_secrets(adapter_name: str, config: dict) -> str:
            """Merge secrets from ~/.ztc/secrets with config"""
            secrets_file = Path.home() / ".ztc" / "secrets"
            if not secrets_file.exists():
                return json.dumps({"merged_config": config})
            try:
                import configparser
                import base64
                parser = configparser.ConfigParser()
                parser.read(secrets_file)
                if adapter_name in parser.sections():
                    merged = config.copy()
                    for key, value in parser.items(adapter_name):
                        if value.startswith("base64:"):
                            merged[key] = base64.b64decode(value[7:]).decode()
                        else:
                            merged[key] = value
                    return json.dumps({"merged_config": merged})
                return json.dumps({"merged_config": config})
            except Exception as e:
                return json.dumps({"error": str(e), "merged_config": config})
