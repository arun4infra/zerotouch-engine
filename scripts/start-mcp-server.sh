#!/usr/bin/env bash
# MCP Server startup script

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Add libs to PYTHONPATH
export PYTHONPATH="${PROJECT_ROOT}/libs:${PYTHONPATH}"

# Run MCP server
cd "$PROJECT_ROOT"
python3 -m workflow_mcp "$@"
