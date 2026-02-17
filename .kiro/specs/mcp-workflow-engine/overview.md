> # Critical Misunderstanding - Need Clarification

## Current State (What I Analyzed):
- **CLI has NO adapters** - they're in libs/workflow_engine/adapters/ ✅
Correct
- **CLI has traditional commands** - init, render, bootstrap that directly
call workflow_engine ❌ This is the issue

## Your Vision (What Should Be):
bash
# ALL commands go through MCP server
ztc init       → MCP tool: collect_configuration → platform.yaml
ztc render     → MCP tool: render_adapters → platform/generated/
ztc bootstrap  → MCP tool: execute_bootstrap → cluster deployed
ztc validate   → MCP tool: validate_artifacts → validation report


CLI is just a thin MCP client - no business logic, only:
1. Parse user input
2. Call MCP tool
3. Display response

## Gap in Current Implementation:

The workflow_mcp server currently only exposes 4 workflow tools:
- start_workflow
- submit_answer
- restore_session
- restart_workflow

Missing MCP tools for traditional pipeline:
- ❌ render_adapters tool
- ❌ execute_bootstrap tool
- ❌ validate_artifacts tool
- ❌ collect_configuration tool (for init)

## What Needs to Happen:

1. Add MCP tools to libs/workflow_mcp/workflow_server/mcp_server.py:
   - collect_configuration() - replaces init command logic
   - render_adapters() - replaces render command logic
   - execute_bootstrap() - replaces bootstrap command logic
   - validate_artifacts() - replaces validate command logic

2. Refactor CLI commands in libs/cli/commands/ to be thin wrappers:
   - Remove all business logic
   - Just call MCP tools
   - Display results

This is a MAJOR architectural gap not covered in my analysis. The MCP server
needs to expose the entire adapter lifecycle, not just workflow navigation.