"""Bootstrap handler for MCP tools"""

import json
from pathlib import Path
from workflow_engine.engine import BootstrapExecutor


class BootstrapHandler:
    def __init__(self, mcp, allow_write: bool = False):
        self.mcp = mcp
        self.allow_write = allow_write
        self._register_tools()
    
    def _register_tools(self):
        @self.mcp.tool()
        async def execute_stage(pipeline_yaml_path: str, stage_name: str, skip_cache: bool = False) -> str:
            """Execute a bootstrap stage"""
            if not self.allow_write:
                return json.dumps({"error": "Write operations not allowed. Use --allow-write flag"})
            try:
                executor = BootstrapExecutor(Path(pipeline_yaml_path))
                result = await executor.execute_stage(stage_name, skip_cache=skip_cache)
                return json.dumps({
                    "success": result.success,
                    "stage": result.stage_name,
                    "output": result.output,
                    "error": result.error,
                    "cached": result.cached
                })
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})
        
        @self.mcp.tool()
        async def get_stage_status(pipeline_yaml_path: str, stage_name: str) -> str:
            """Get status of a bootstrap stage"""
            try:
                executor = BootstrapExecutor(Path(pipeline_yaml_path))
                status = executor.get_stage_status(stage_name)
                return json.dumps({"stage": stage_name, "status": status})
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        @self.mcp.tool()
        async def list_stages(pipeline_yaml_path: str) -> str:
            """List all bootstrap stages"""
            try:
                executor = BootstrapExecutor(Path(pipeline_yaml_path))
                stages = executor.list_stages()
                return json.dumps({"stages": stages})
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        @self.mcp.tool()
        async def rollback_stage(pipeline_yaml_path: str, stage_name: str) -> str:
            """Rollback a bootstrap stage"""
            if not self.allow_write:
                return json.dumps({"error": "Write operations not allowed. Use --allow-write flag"})
            try:
                executor = BootstrapExecutor(Path(pipeline_yaml_path))
                success = await executor.rollback_stage(stage_name)
                return json.dumps({"success": success, "stage": stage_name})
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})
