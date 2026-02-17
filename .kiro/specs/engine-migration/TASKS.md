# Implementation Tasks

This document breaks down the migration into actionable tasks with time estimates.

## Phase 1: Critical Gaps (Week 1 - 22 hours)

### Task 1.1: Port DependencyResolver (4 hours)
**File**: `libs/workflow_engine/engine/resolver.py`
**Source**: `legacy/ztc/engine/resolver.py`

**Subtasks**:
- [ ] Create `libs/workflow_engine/engine/` directory
- [ ] Copy `DependencyResolver` class (lines 1-100)
- [ ] Copy exception classes: `MissingCapabilityError`, `CircularDependencyError`
- [ ] Update imports to new module paths
- [ ] Add unit tests for topological sort
- [ ] Add unit tests for circular dependency detection
- [ ] Add unit tests for phase-based ordering

**Acceptance Criteria**:
- Adapters execute in correct dependency order
- Circular dependencies detected and reported
- Phase ordering respected (foundation → gitops → runtime)

---

### Task 1.2: Create BootstrapExecutor (8 hours)
**File**: `libs/workflow_engine/engine/bootstrap_executor.py`
**Source**: `legacy/ztc/commands/bootstrap.py` (lines 50-200)

**Subtasks**:
- [ ] Create `BootstrapExecutor` class
- [ ] Implement `is_stage_cached(cache_key)` method
- [ ] Implement `mark_stage_cached(cache_key)` method
- [ ] Implement `wait_for_barrier(barrier)` method
- [ ] Implement `execute_stage(stage, retry_count)` method
- [ ] Add exponential backoff retry logic
- [ ] Add stage timing metrics
- [ ] Add unit tests for caching
- [ ] Add unit tests for barriers
- [ ] Add unit tests for retry logic

**Acceptance Criteria**:
- Stages cache correctly to `.zerotouch-cache/stage-cache/`
- Barriers wait for correct conditions
- Failed stages retry with exponential backoff
- Metrics captured for each stage

---

### Task 1.3: Create PipelineGenerator (6 hours)
**File**: `libs/workflow_engine/engine/pipeline_generator.py`
**Source**: `legacy/ztc/engine/engine.py` (lines 400-500)

**Subtasks**:
- [ ] Create `PipelineGenerator` class
- [ ] Implement `generate_pipeline_yaml(adapters)` method
- [ ] Implement `write_debug_scripts(adapters, output_dir)` method
- [ ] Implement `validate_artifacts(generated_dir)` method
- [ ] Add unit tests for pipeline generation
- [ ] Add unit tests for debug script extraction
- [ ] Add unit tests for artifact validation

**Acceptance Criteria**:
- `pipeline.yaml` generated with all stages
- Debug scripts extracted to `platform/generated/debug/scripts/`
- Artifacts validated before atomic swap

---

### Task 1.4: Port ScriptExecutor (4 hours)
**File**: `libs/workflow_engine/engine/script_executor.py`
**Source**: `legacy/ztc/engine/script_executor.py`

**Subtasks**:
- [ ] Copy `ScriptExecutor` class
- [ ] Copy `ExecutionResult` dataclass
- [ ] Update imports to new module paths
- [ ] Add execution logging to `.zerotouch-cache/init-logs/`
- [ ] Add script tree copying logic
- [ ] Add unit tests for script execution
- [ ] Add unit tests for context file creation
- [ ] Add unit tests for timeout handling

**Acceptance Criteria**:
- Scripts execute with context files
- Execution logs written to cache directory
- Script tree copied to preserve relative imports
- Timeouts handled gracefully

---

## Phase 2: MCP Handlers (Week 2 - 24 hours)

### Task 2.1: Create AdapterHandler (4 hours)
**File**: `libs/workflow_mcp/handlers/adapter_handler.py`

**Subtasks**:
- [ ] Create `AdapterHandler` class
- [ ] Implement `list_adapters()` tool
- [ ] Implement `get_adapter_inputs(adapter_name)` tool
- [ ] Implement `validate_adapter_config(adapter_name, config)` tool
- [ ] Implement `get_adapter_metadata(adapter_name)` tool
- [ ] Register tools with MCP server
- [ ] Add error handling for all tools

**Acceptance Criteria**:
- All 4 tools callable from MCP client
- Tools return correct data structures
- Errors handled gracefully

---

### Task 2.2: Create PlatformHandler (4 hours)
**File**: `libs/workflow_mcp/handlers/platform_handler.py`

**Subtasks**:
- [ ] Create `PlatformHandler` class
- [ ] Implement `generate_platform_yaml(adapters_config)` tool
- [ ] Implement `validate_platform_yaml(yaml_path)` tool
- [ ] Implement `get_platform_status()` tool
- [ ] Implement `merge_secrets(platform_yaml, secrets_file)` tool
- [ ] Register tools with MCP server
- [ ] Add error handling for all tools

**Acceptance Criteria**:
- All 4 tools callable from MCP client
- `platform.yaml` generated correctly
- Secrets merged from `~/.ztc/secrets`

---

### Task 2.3: Create RenderHandler (6 hours)
**File**: `libs/workflow_mcp/handlers/render_handler.py`

**Subtasks**:
- [ ] Create `RenderHandler` class
- [ ] Implement `render_adapters(platform_yaml, partial, debug)` tool
- [ ] Implement `generate_pipeline_yaml(platform_yaml)` tool
- [ ] Implement `generate_lock_file(platform_yaml, artifacts_hash)` tool
- [ ] Implement `extract_debug_scripts(platform_yaml)` tool
- [ ] Integrate with `DependencyResolver`
- [ ] Integrate with `PipelineGenerator`
- [ ] Register tools with MCP server
- [ ] Add error handling for all tools

**Acceptance Criteria**:
- All 4 tools callable from MCP client
- Adapters rendered in correct order
- Pipeline YAML generated
- Lock file created with hashes

---

### Task 2.4: Create BootstrapHandler (6 hours)
**File**: `libs/workflow_mcp/handlers/bootstrap_handler.py`

**Subtasks**:
- [ ] Create `BootstrapHandler` class
- [ ] Implement `execute_stage(stage_name, context, cache_enabled, retry_count)` tool
- [ ] Implement `get_stage_status(stage_name)` tool
- [ ] Implement `list_stages(pipeline_yaml)` tool
- [ ] Implement `rollback_stage(stage_name)` tool
- [ ] Integrate with `BootstrapExecutor`
- [ ] Register tools with MCP server
- [ ] Add error handling for all tools

**Acceptance Criteria**:
- All 4 tools callable from MCP client
- Stages execute with caching
- Stage status queryable
- Rollback works for failed stages

---

### Task 2.5: Create ValidationHandler (4 hours)
**File**: `libs/workflow_mcp/handlers/validation_handler.py`

**Subtasks**:
- [ ] Create `ValidationHandler` class
- [ ] Implement `validate_artifacts(lock_file)` tool
- [ ] Implement `validate_runtime_dependencies()` tool
- [ ] Implement `validate_cluster_access(kubeconfig)` tool
- [ ] Register tools with MCP server
- [ ] Add error handling for all tools

**Acceptance Criteria**:
- All 3 tools callable from MCP client
- Artifacts validated against lock file
- Runtime dependencies checked
- Cluster access validated

---

## Phase 3: CLI Refactoring (Week 3 - 14 hours)

### Task 3.1: Refactor init Command (4 hours)
**File**: `libs/cli/commands/init.py`

**Subtasks**:
- [ ] Remove business logic (adapter registry, input collection)
- [ ] Add MCP tool calls: `list_adapters`, `get_adapter_inputs`, `generate_platform_yaml`
- [ ] Keep only UI/UX logic (prompts, progress bars, error display)
- [ ] Add error handling for tool call failures
- [ ] Test with local MCP server

**Acceptance Criteria**:
- Command orchestrates MCP tools
- No business logic in CLI
- Same UX as before
- `platform.yaml` generated correctly

---

### Task 3.2: Refactor render Command (4 hours)
**File**: `libs/cli/commands/render.py`

**Subtasks**:
- [ ] Remove business logic (adapter rendering, pipeline generation)
- [ ] Add MCP tool calls: `validate_platform_yaml`, `render_adapters`, `generate_pipeline_yaml`, `generate_lock_file`
- [ ] Keep only UI/UX logic (progress bars, success messages)
- [ ] Add error handling for tool call failures
- [ ] Test with local MCP server

**Acceptance Criteria**:
- Command orchestrates MCP tools
- No business logic in CLI
- Same UX as before
- Artifacts generated correctly

---

### Task 3.3: Refactor bootstrap Command (4 hours)
**File**: `libs/cli/commands/bootstrap.py`

**Subtasks**:
- [ ] Remove business logic (stage execution, caching)
- [ ] Add MCP tool calls: `validate_artifacts`, `list_stages`, `execute_stage`
- [ ] Keep only UI/UX logic (progress bars, stage status display)
- [ ] Add error handling for tool call failures
- [ ] Test with local MCP server

**Acceptance Criteria**:
- Command orchestrates MCP tools
- No business logic in CLI
- Same UX as before
- Bootstrap completes successfully

---

### Task 3.4: Refactor validate Command (2 hours)
**File**: `libs/cli/commands/validate.py`

**Subtasks**:
- [ ] Remove business logic (hash validation)
- [ ] Add MCP tool calls: `validate_artifacts`, `validate_cluster_access`
- [ ] Keep only UI/UX logic (validation results display)
- [ ] Add error handling for tool call failures
- [ ] Test with local MCP server

**Acceptance Criteria**:
- Command orchestrates MCP tools
- No business logic in CLI
- Same UX as before
- Validation passes

---

## Phase 4: Integration & Testing (Week 4 - 16 hours)

### Task 4.1: Update MCP Server Registration (2 hours)
**File**: `libs/workflow_mcp/workflow_server/mcp_server.py`

**Subtasks**:
- [ ] Import all handlers
- [ ] Register `AdapterHandler`
- [ ] Register `PlatformHandler`
- [ ] Register `RenderHandler`
- [ ] Register `BootstrapHandler`
- [ ] Register `ValidationHandler`
- [ ] Add `--allow-write` flag support
- [ ] Test server startup

**Acceptance Criteria**:
- All handlers registered
- All tools discoverable
- Server starts without errors

---

### Task 4.2: Update MCP Client (2 hours)
**File**: `libs/cli/mcp_client.py`

**Subtasks**:
- [ ] Add methods for new tools
- [ ] Add error handling for tool calls
- [ ] Add retry logic for transient failures
- [ ] Add logging for debugging

**Acceptance Criteria**:
- All tools callable from client
- Errors handled gracefully
- Retries work for transient failures

---

### Task 4.3: Test 1 - CLI E2E (4 hours)

**Setup**:
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

**Subtasks**:
- [ ] Test `ztc init` - generates `platform.yaml`
- [ ] Test `ztc render` - generates artifacts
- [ ] Test `ztc bootstrap` - deploys cluster
- [ ] Test `ztc validate` - validates artifacts
- [ ] Document any issues found
- [ ] Fix critical bugs

**Acceptance Criteria**:
- All commands complete successfully
- Artifacts match legacy output
- No errors in logs

---

### Task 4.4: Test 2 - IDE Chat (4 hours)

**Setup**:
```bash
# Terminal 1: Start MCP server
cd libs/workflow_mcp
python -m workflow_mcp.workflow_server.mcp_server --allow-write

# Configure Claude Desktop
# Add to ~/.config/claude/claude_desktop_config.json
```

**Subtasks**:
- [ ] Test tool discovery in IDE
- [ ] Test "List adapters" chat interaction
- [ ] Test "Get adapter inputs" chat interaction
- [ ] Test "Generate platform.yaml" chat interaction
- [ ] Test "Render platform" chat interaction
- [ ] Test "Execute bootstrap" chat interaction
- [ ] Document any issues found
- [ ] Fix critical bugs

**Acceptance Criteria**:
- IDE discovers all tools
- AI can call tools correctly
- AI can orchestrate workflows
- Same artifacts as CLI test

---

### Task 4.5: Bug Fixes & Polish (4 hours)

**Subtasks**:
- [ ] Fix bugs found in testing
- [ ] Improve error messages
- [ ] Add missing logging
- [ ] Update documentation
- [ ] Create demo video

**Acceptance Criteria**:
- All critical bugs fixed
- Error messages clear and actionable
- Logging comprehensive
- Documentation complete

---

## Summary

| Phase | Tasks | Hours | Dependencies |
|-------|-------|-------|--------------|
| Phase 1: Critical Gaps | 4 | 22 | None |
| Phase 2: MCP Handlers | 5 | 24 | Phase 1 |
| Phase 3: CLI Refactoring | 4 | 14 | Phase 2 |
| Phase 4: Integration & Testing | 5 | 16 | Phase 3 |
| **Total** | **18** | **76** | - |

## Task Assignment Recommendations

**Developer 1** (Backend Focus):
- Phase 1: All tasks (22 hours)
- Phase 2: Tasks 2.1, 2.3, 2.4 (14 hours)
- Phase 4: Task 4.1 (2 hours)
- **Total**: 38 hours

**Developer 2** (Full-Stack Focus):
- Phase 2: Tasks 2.2, 2.5 (8 hours)
- Phase 3: All tasks (14 hours)
- Phase 4: Tasks 4.2, 4.3, 4.4, 4.5 (14 hours)
- **Total**: 36 hours

## Daily Standup Template

**What did you complete yesterday?**
- Task X.Y: [Status]

**What will you work on today?**
- Task X.Y: [Plan]

**Any blockers?**
- [Blocker description]

## Weekly Demo Checklist

**Week 1 Demo**:
- [ ] DependencyResolver working
- [ ] BootstrapExecutor with caching working
- [ ] PipelineGenerator working
- [ ] ScriptExecutor working

**Week 2 Demo**:
- [ ] All MCP handlers registered
- [ ] All tools callable from MCP client
- [ ] Sample tool calls demonstrated

**Week 3 Demo**:
- [ ] All CLI commands refactored
- [ ] CLI orchestrates MCP tools
- [ ] Same UX as before

**Week 4 Demo**:
- [ ] Test 1 (CLI E2E) passing
- [ ] Test 2 (IDE Chat) passing
- [ ] Demo video created
