"""Init workflow handler for MCP tools"""

import json
from workflow_engine.registry import AdapterRegistry
from workflow_engine.engine.init_workflow import InitWorkflow


class InitWorkflowHandler:
    def __init__(self, mcp, allow_write: bool = False):
        self.mcp = mcp
        self.allow_write = allow_write
        self.workflow = InitWorkflow(AdapterRegistry())
        self._register_tools()
    
    def _register_tools(self):
        @self.mcp.tool()
        async def init_start() -> str:
            """Start platform init workflow"""
            try:
                result = self.workflow.start()
                # Serialize workflow_state to JSON string for CLI
                if "workflow_state" in result:
                    result["workflow_state"] = json.dumps(result["workflow_state"])
                return json.dumps(result)
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        @self.mcp.tool()
        async def init_answer(workflow_state: str, answer_value: str) -> str:
            """Submit answer and get next question"""
            try:
                state = json.loads(workflow_state)
                
                # Check write permission for final YAML generation
                if state.get("current_group_index", -1) >= len(state.get("selection_groups", [])) and not self.allow_write:
                    return json.dumps({"error": "Write operations not allowed"})
                
                result = self.workflow.answer(state, answer_value)
                # Serialize workflow_state to JSON string for CLI
                if "workflow_state" in result:
                    result["workflow_state"] = json.dumps(result["workflow_state"])
                return json.dumps(result)
            except Exception as e:
                return json.dumps({"error": str(e)})
