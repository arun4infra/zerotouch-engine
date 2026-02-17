"""MCP Server entry point for workflow engine"""
import asyncio
import sys
from pathlib import Path
from typing import Optional

from workflow_mcp.workflow_server.mcp_server import WorkflowMCPServer


def main() -> None:
    """Main entry point for MCP server"""
    # Parse command line arguments
    transport = "stdio"  # Default to stdio
    host: Optional[str] = None
    port = 8000
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--http":
            transport = "http"
            if len(sys.argv) > 2:
                port = int(sys.argv[2])
    
    # Get workflow base path from environment or use default
    import os
    workflow_base_path = Path(os.getenv("ZTC_WORKFLOW_BASE_PATH", "workflows"))
    
    # Initialize server
    server = WorkflowMCPServer(workflow_base_path=workflow_base_path)
    
    # Run server
    if transport == "stdio":
        asyncio.run(server.run_stdio())
    else:
        asyncio.run(server.run_http(host=host, port=port))


if __name__ == "__main__":
    main()
