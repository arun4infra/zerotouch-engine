# CLI Migration Plan 3 - Executive Summary

## What This Spec Delivers

A complete migration plan to transform the CLI from a monolithic fat client into a thin MCP orchestrator, following industry-standard patterns from AWS and Kubernetes MCP servers.

## The Problem

Current architecture has business logic split between CLI and MCP server:
- CLI has adapters, rendering, bootstrap logic (fat client)
- MCP server only has workflow navigation (thin server)
- Cannot test via IDE chat (tools too limited)
- Violates MCP best practices (tools should be granular operations, not workflows)

## The Solution

**Invert the architecture**:
- CLI becomes thin orchestrator (only UI/UX)
- MCP server becomes rich tool provider (all business logic)
- Workflow engine remains standalone (core logic)

## Key Architectural Changes

### Before
```
CLI (Fat) → Workflow Engine (Embedded)
MCP Server (Thin) → Only workflow tools
```

### After
```
CLI (Thin) → MCP Server (Rich) → Workflow Engine (Standalone)
IDE (Chat) → MCP Server (Rich) → Workflow Engine (Standalone)
```

## What Gets Built

### 4 New Engine Components
1. **DependencyResolver** - Adapter execution ordering (4 hours)
2. **BootstrapExecutor** - Stage caching & barriers (8 hours)
3. **PipelineGenerator** - Pipeline YAML generation (6 hours)
4. **ScriptExecutor** - Script execution with logging (4 hours)

### 5 New MCP Handlers (19 Tools Total)
1. **AdapterHandler** - 4 tools (list, get inputs, validate, metadata)
2. **PlatformHandler** - 4 tools (generate yaml, validate, status, merge secrets)
3. **RenderHandler** - 4 tools (render, pipeline yaml, lock file, debug scripts)
4. **BootstrapHandler** - 4 tools (execute stage, status, list, rollback)
5. **ValidationHandler** - 3 tools (artifacts, dependencies, cluster access)

### 4 Refactored CLI Commands
1. **init** - Orchestrates: list_adapters → get_inputs → generate_yaml
2. **render** - Orchestrates: validate_yaml → render → pipeline → lock
3. **bootstrap** - Orchestrates: validate → list_stages → execute_stage (loop)
4. **validate** - Orchestrates: validate_artifacts → validate_cluster

## Two Test Scenarios

### Test 1: CLI → MCP → Engine (Local E2E)
```bash
# Terminal 1: MCP server
python -m workflow_mcp.workflow_server.mcp_server --allow-write

# Terminal 2: CLI
ztc init      # Generates platform.yaml
ztc render    # Generates artifacts
ztc bootstrap # Deploys cluster
ztc validate  # Validates deployment
```

### Test 2: IDE → MCP → Engine (Chat-Driven)
```bash
# Terminal 1: MCP server
python -m workflow_mcp.workflow_server.mcp_server --allow-write

# Claude Desktop: Chat
"List adapters" → AI calls list_adapters tool
"Generate platform.yaml with hetzner, cilium, talos" → AI orchestrates
"Render the platform" → AI calls render tools
"Execute bootstrap" → AI calls bootstrap tools
```

## Implementation Timeline

| Week | Focus | Hours | Deliverable |
|------|-------|-------|-------------|
| 1 | Critical gaps | 22 | Engine components working |
| 2 | MCP handlers | 24 | All 19 tools callable |
| 3 | CLI refactoring | 14 | Thin orchestrators |
| 4 | Testing & polish | 16 | Both tests passing |
| **Total** | **4 weeks** | **76** | **Production ready** |

## Success Criteria

- ✅ **Zero business logic in CLI** - All logic in engine/handlers
- ✅ **All tools callable from IDE** - AI can orchestrate workflows
- ✅ **Test 1 passes** - CLI E2E works locally
- ✅ **Test 2 passes** - IDE chat works locally
- ✅ **Same artifacts as legacy** - Backward compatibility

## Why This Matters

### Enables AI-Driven Infrastructure
- AI agents can orchestrate complex workflows via chat
- No CLI required - just natural language
- Tools are composable - AI can create new workflows

### Follows Industry Standards
- AWS MCP servers use this pattern (EKS, Lambda, etc.)
- Kubernetes MCP server uses this pattern
- FastMCP framework designed for this

### Better Architecture
- Clear separation of concerns
- Testable components
- Scalable (MCP server can be deployed remotely)
- Maintainable (business logic in one place)

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Tool granularity too fine | Batch operations where possible |
| State management complexity | Comprehensive logging |
| Breaking changes | Maintain backward compatibility |
| Performance degradation | Profile and optimize |

## Next Steps

1. **Review this spec** - Approve architecture and timeline
2. **Assign tasks** - 2 developers, 4 weeks
3. **Daily standups** - Track progress
4. **Weekly demos** - Show working features
5. **Final testing** - Both scenarios pass

## Documents in This Spec

1. **SPECIFICATION.md** - Detailed architecture and design
2. **TOOLS_API.md** - Complete API reference for 19 tools
3. **TASKS.md** - 18 implementation tasks with estimates
4. **README.md** - Quick start guide

## Questions?

- Architecture questions → Review SPECIFICATION.md
- Tool design questions → Review TOOLS_API.md
- Implementation questions → Review TASKS.md
- General questions → Contact migration team

---

**Prepared**: February 18, 2026
**Estimated Effort**: 76 hours (4 weeks with 2 developers)
**Target Completion**: March 18, 2026
