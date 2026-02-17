# CLI Migration Plan 3 - Specification

This directory contains the complete specification for migrating the CLI from a monolithic architecture to a thin MCP client that orchestrates workflows by calling granular MCP tools.

## Documents

### 1. [SPECIFICATION.md](./SPECIFICATION.md)
**Main migration specification** covering:
- Architecture changes (before/after)
- Critical gaps to address
- MCP server tool design
- CLI command refactoring patterns
- File structure changes
- Test scenarios
- Implementation phases
- Success metrics

### 2. [TOOLS_API.md](./TOOLS_API.md)
**MCP tools API reference** defining:
- All 19 MCP tools exposed by the server
- Tool parameters and return types
- Error handling patterns
- Access control (read-only vs write)
- Tool invocation examples

### 3. [TASKS.md](./TASKS.md)
**Implementation tasks breakdown** with:
- 18 detailed tasks across 4 phases
- Time estimates (76 hours total)
- Acceptance criteria for each task
- Task dependencies
- Developer assignment recommendations
- Daily standup template
- Weekly demo checklist

## Quick Start

### For Reviewers
1. Read [SPECIFICATION.md](./SPECIFICATION.md) for high-level overview
2. Review [TOOLS_API.md](./TOOLS_API.md) for tool design
3. Check [TASKS.md](./TASKS.md) for implementation plan

### For Developers
1. Review [TASKS.md](./TASKS.md) for your assigned tasks
2. Reference [TOOLS_API.md](./TOOLS_API.md) for tool contracts
3. Follow [SPECIFICATION.md](./SPECIFICATION.md) for architecture guidance

## Key Changes

### Architecture
- **CLI**: Fat client → Thin orchestrator
- **MCP Server**: Workflow-only → Rich tool provider
- **Workflow Engine**: Embedded → Standalone service

### Critical Gaps Addressed
1. **DependencyResolver** - Adapter execution ordering
2. **BootstrapExecutor** - Stage caching and barriers
3. **PipelineGenerator** - Pipeline YAML generation
4. **ScriptExecutor** - Script execution with logging

### New MCP Handlers
1. **AdapterHandler** - Adapter operations (4 tools)
2. **PlatformHandler** - Platform config (4 tools)
3. **RenderHandler** - Artifact generation (4 tools)
4. **BootstrapHandler** - Deployment (4 tools)
5. **ValidationHandler** - Validation (3 tools)

## Test Scenarios

### Test 1: CLI → MCP Server → Workflow Engine
```bash
# Terminal 1: Start MCP server
cd libs/workflow_mcp
python -m workflow_mcp.workflow_server.mcp_server --allow-write

# Terminal 2: Run CLI
cd libs/cli
ztc init
ztc render
ztc bootstrap
ztc validate
```

### Test 2: IDE → MCP Server → Workflow Engine
```bash
# Terminal 1: Start MCP server
cd libs/workflow_mcp
python -m workflow_mcp.workflow_server.mcp_server --allow-write

# Configure Claude Desktop with MCP server
# Chat with AI to orchestrate workflows
```

## Implementation Timeline

| Phase | Duration | Focus |
|-------|----------|-------|
| Phase 1 | Week 1 | Critical gaps (22 hours) |
| Phase 2 | Week 2 | MCP handlers (24 hours) |
| Phase 3 | Week 3 | CLI refactoring (14 hours) |
| Phase 4 | Week 4 | Testing & polish (16 hours) |
| **Total** | **4 weeks** | **76 hours** |

## Success Criteria

- ✅ Zero business logic in CLI
- ✅ All tools callable from IDE
- ✅ Test 1 passes (CLI E2E)
- ✅ Test 2 passes (IDE Chat)
- ✅ Same artifacts as legacy

## Related Documents

- [Migration Gap Analysis](../../../MIGRATION_GAP_ANALYSIS.md)
- [Implementation Checklist](../../../IMPLEMENTATION_CHECKLIST.md)
- [Migration Summary](../../../MIGRATION_SUMMARY.md)

## Questions?

Contact the migration team or review the related documents above.
