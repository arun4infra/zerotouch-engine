"""Render handler for MCP tools"""

import json
from pathlib import Path
from workflow_engine.engine import PlatformEngine


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
            """Generate pipeline.yaml from adapters"""
            try:
                engine = PlatformEngine(Path(platform_yaml_path))
                adapters = engine.resolve_adapters()
                workspace = Path(".zerotouch-cache/workspace")
                workspace.mkdir(parents=True, exist_ok=True)
                engine.generate_pipeline_yaml(adapters, workspace)
                pipeline_path = workspace / "pipeline.yaml"
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
        
        @self.mcp.tool()
        async def extract_debug_scripts(platform_yaml_path: str) -> str:
            """Extract debug scripts from adapters"""
            try:
                engine = PlatformEngine(Path(platform_yaml_path))
                adapters = engine.resolve_adapters()
                generated_dir = Path("platform/generated")
                if not generated_dir.exists():
                    return json.dumps({"success": False, "error": "No generated artifacts found"})
                engine.write_debug_scripts(adapters, generated_dir)
                return json.dumps({"success": True, "message": "Debug scripts extracted"})
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})
