"""Adapter handler for MCP tools"""

import json
from pathlib import Path
from workflow_engine.registry import AdapterRegistry


class AdapterHandler:
    def __init__(self, mcp, allow_write: bool = False):
        self.mcp = mcp
        self.allow_write = allow_write
        self.registry = AdapterRegistry()
        self._register_tools()
    
    def _register_tools(self):
        @self.mcp.tool()
        async def list_adapters() -> str:
            """List all available adapters"""
            adapters = []
            for name in self.registry.list_adapters():
                metadata = self.registry.get_metadata(name)
                adapters.append({
                    "name": name,
                    "version": metadata.get("version", "unknown"),
                    "description": metadata.get("description", ""),
                    "phase": metadata.get("phase", 0)
                })
            return json.dumps({"adapters": adapters})
        
        @self.mcp.tool()
        async def get_adapter_inputs(adapter_name: str) -> str:
            """Get input schema for an adapter"""
            try:
                adapter_class = self.registry.get_adapter_class(adapter_name)
                temp_instance = adapter_class({})
                inputs = temp_instance.get_input_schema() if hasattr(temp_instance, 'get_input_schema') else []
                return json.dumps({"adapter": adapter_name, "inputs": inputs})
            except KeyError as e:
                return json.dumps({"error": str(e)})
        
        @self.mcp.tool()
        async def validate_adapter_config(adapter_name: str, config: dict) -> str:
            """Validate adapter configuration"""
            try:
                adapter = self.registry.get_adapter(adapter_name, config)
                return json.dumps({"valid": True, "adapter": adapter_name})
            except Exception as e:
                return json.dumps({"valid": False, "error": str(e)})
        
        @self.mcp.tool()
        async def get_adapter_metadata(adapter_name: str) -> str:
            """Get adapter metadata"""
            try:
                metadata = self.registry.get_metadata(adapter_name)
                return json.dumps({"adapter": adapter_name, "metadata": metadata})
            except KeyError as e:
                return json.dumps({"error": str(e)})
