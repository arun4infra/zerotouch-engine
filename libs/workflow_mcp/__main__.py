"""MCP Server entry point for workflow engine"""
import argparse
from pathlib import Path

from workflow_mcp.workflow_server.mcp_server import WorkflowMCPServer


def main() -> None:
    """Main entry point for MCP server"""
    parser = argparse.ArgumentParser(description="Workflow MCP Server")
    parser.add_argument("--allow-write", action="store_true", help="Allow write operations (render, bootstrap)")
    parser.add_argument("--http", action="store_true", help="Use HTTP transport instead of stdio")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (default: 8000)")
    parser.add_argument("--workflow-path", type=str, default="workflows", help="Base path for workflows")
    
    args = parser.parse_args()
    
    # Get workflow base path
    workflow_base_path = Path(args.workflow_path)
    
    # Initialize server with allow_write flag
    server = WorkflowMCPServer(workflow_base_path=workflow_base_path, allow_write=args.allow_write)
    
    # Run server (FastMCP handles async internally)
    if args.http:
        server.mcp.run(transport="streamable-http", port=args.port)
    else:
        server.mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
