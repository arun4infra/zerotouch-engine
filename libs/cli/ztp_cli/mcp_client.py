"""MCP Client for workflow engine communication"""
import os
import json
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, Optional, List
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool


class WorkflowMCPClient:
    """MCP Client for workflow engine"""
    
    def __init__(
        self,
        server_command: str = "uv",
        server_args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None
    ):
        """Initialize MCP client
        
        Args:
            server_command: Command to run MCP server
            server_args: Arguments for server command
            env: Environment variables to pass to server
        """
        self.server_command = server_command
        self.server_args = server_args or ["run", "-m", "workflow_mcp"]
        self.env = env or {}
        self._tools: List[Tool] = []
    
    @asynccontextmanager
    async def connect(self) -> AsyncIterator[ClientSession]:
        """Connect to MCP server via stdio
        
        Yields:
            ClientSession for making tool calls
        """
        # Merge current environment with custom env
        server_env = os.environ.copy()
        server_env.update(self.env)
        
        # Create server parameters
        server_params = StdioServerParameters(
            command=self.server_command,
            args=self.server_args,
            env=server_env
        )
        
        # Connect to server
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize session
                await session.initialize()
                
                # List available tools
                tools_response = await session.list_tools()
                self._tools = tools_response.tools
                
                yield session
    
    async def list_tools(self, session: ClientSession) -> List[Tool]:
        """List available tools from server
        
        Args:
            session: Active client session
            
        Returns:
            List of available tools
        """
        response = await session.list_tools()
        return response.tools
    
    async def call_tool(
        self,
        session: ClientSession,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call MCP tool and return result
        
        Args:
            session: Active client session
            tool_name: Name of tool to call
            arguments: Tool arguments
            
        Returns:
            Tool result as dictionary
            
        Raises:
            ValueError: If tool call fails or returns invalid content
        """
        try:
            result = await session.call_tool(tool_name, arguments)
            
            # Process result content
            if not result.content:
                raise ValueError(f"Tool {tool_name} returned no content")
            
            # Extract content from result
            for item in result.content:
                # Handle text content
                if hasattr(item, 'text') and item.text:
                    try:
                        return json.loads(item.text)
                    except json.JSONDecodeError:
                        # If not JSON, return as-is in dict
                        return {"result": item.text}
                
                # Handle other content types if needed
                if hasattr(item, 'type'):
                    if item.type == "text":
                        return {"result": getattr(item, 'text', '')}
            
            raise ValueError(f"Tool {tool_name} returned unprocessable content")
            
        except Exception as e:
            raise ValueError(f"Tool call failed: {str(e)}") from e
    
    @property
    def tools(self) -> List[Tool]:
        """Get cached list of available tools
        
        Returns:
            List of tools discovered during connection
        """
        return self._tools


def get_default_client(workflow_base_path: Optional[Path] = None) -> WorkflowMCPClient:
    """Get default MCP client with current environment
    
    Args:
        workflow_base_path: Base path for workflows
        
    Returns:
        Configured WorkflowMCPClient
    """
    env = {}
    
    # Pass workflow base path if specified
    if workflow_base_path:
        env["ZTC_WORKFLOW_BASE_PATH"] = str(workflow_base_path)
    
    # Pass context file path if set
    if "ZTC_CONTEXT_FILE" in os.environ:
        env["ZTC_CONTEXT_FILE"] = os.environ["ZTC_CONTEXT_FILE"]
    
    return WorkflowMCPClient(env=env)
