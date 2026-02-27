"""Render handler for MCP tools"""

import json
from pathlib import Path
from workflow_engine.engine import PlatformEngine, generate_bootstrap_pipeline


class RenderHandler:
    def __init__(self, mcp, allow_write: bool = False):
        self.mcp = mcp
        self.allow_write = allow_write
        self._register_tools()
    
    def _register_tools(self):
        @self.mcp.tool()
        async def render_adapters(platform_yaml_path: str, partial: list = None, debug: bool = False) -> str:
            """Render platform adapters"""
            if not self.allow_write:
                return json.dumps({"error": "Write operations not allowed. Use --allow-write flag"})
            try:
                engine = PlatformEngine(Path(platform_yaml_path), debug=debug)
                await engine.render(partial=partial)
                return json.dumps({"success": True, "message": "Render completed"})
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})
        
        @self.mcp.tool()
        async def generate_pipeline_yaml(platform_yaml_path: str) -> str:
            """Generate pipeline.yaml from platform.yaml"""
            try:
                platform_path = Path(platform_yaml_path)
                pipeline_path = Path("platform/pipeline.yaml")
                generate_bootstrap_pipeline(platform_path, pipeline_path)
                with open(pipeline_path, 'r') as f:
                    content = f.read()
                return json.dumps({"success": True, "pipeline_yaml": content})
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})
        
        @self.mcp.tool()
        async def generate_lock_file(platform_yaml_path: str) -> str:
            """Generate lock file for rendered artifacts"""
            if not self.allow_write:
                return json.dumps({"error": "Write operations not allowed. Use --allow-write flag"})
            try:
                engine = PlatformEngine(Path(platform_yaml_path))
                adapters = engine.resolve_adapters()
                artifacts_hash = engine.hash_directory(Path("platform/generated"))
                engine.generate_lock_file(artifacts_hash, adapters)
                return json.dumps({"success": True, "message": "Lock file generated"})
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})
