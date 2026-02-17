# CLI Migration Specification - Plan 3

## Overview

This specification defines the migration of the CLI from a monolithic architecture to a thin MCP client that orchestrates workflows by calling granular MCP tools. The migration addresses the critical gaps identified in the analysis and follows industry-standard MCP server patterns from AWS and Kubernetes implementations.

## Goals

1. **Transform CLI into thin MCP client** - Remove all business logic, keep only orchestration
2. **Expose granular MCP tools** - Replace command-based API with tool-based API
3. **Enable two test scenarios**:
   - **Test 1**: CLI → Local MCP Server → Local Workflow Engine (E2E pipeline)
   - **Test 2**: IDE (Claude/Cursor) → Local MCP Server → Local Workflow Engine (Chat-driven pipeline)

## Architecture Changes

### Before (Current State)
```
CLI (Fat Client)
├── Business Logic (init, render, bootstrap, validate)
├── Adapter Registry
├── PlatformEngine
└── Direct workflow_engine imports

MCP Server (Thin)
└── Only workflow navigation tools (start_workflow, submit_answer, etc.)
```

### After (Target State)
```
CLI (Thin Orchestrator)
├── Command handlers (orchestrate tool calls)
└── MCP Client (calls tools)

MCP Server (Rich Tool Provider)
├── AdapterHandler (adapter operations)
├── PlatformHandler (platform config operations)
├── RenderHandler (artifact generation)
├── BootstrapHandler (deployment operations)
└── ValidationHandler (validation operations)

Workflow Engine (Core Logic)
├── All adapters
├── QuestionPathTraverser
├── PlatformEngine (render pipeline)
└── DependencyResolver
```

## Critical Gaps to Address

### 1. DependencyResolver (CRITICAL)
**Location**: `libs/workflow_engine/engine/resolver.py` (NEW FILE)
**Source**: `legacy/ztc/engine/resolver.py`
**Priority**: P0 - Blocks correct adapter execution

**Implementation**:
- Port `DependencyResolver` class with topological sort
- Port `MissingCapabilityError` and `CircularDependencyError`
- Add phase-based ordering (foundation → gitops → runtime)
- Integrate with MCP render tools

### 2. Bootstrap Stage Caching (CRITICAL)
**Location**: `libs/workflow_engine/engine/bootstrap_executor.py` (NEW FILE)
**Priority**: P0 - Blocks production deployment

**Implementation**:
- Create `BootstrapExecutor` class with stage caching
- Implement barrier-based execution (local, cluster_installed, cluster_accessible, cni_ready)
- Add retry logic with exponential backoff
- Integrate with MCP bootstrap tools

### 3. Pipeline YAML Generation (HIGH)
**Location**: `libs/workflow_engine/engine/pipeline_generator.py` (NEW FILE)
**Priority**: P1 - Required for bootstrap

**Implementation**:
- Port `generate_pipeline_yaml()` from legacy
- Port `write_debug_scripts()` for observability
- Port `validate_artifacts()` for safety
- Integrate with MCP render tools

### 4. ScriptExecutor (HIGH)
**Location**: `libs/workflow_engine/engine/script_executor.py` (NEW FILE)
**Priority**: P1 - Reduces code duplication

**Implementation**:
- Port `ScriptExecutor` class with logging
- Add script tree copying for relative imports
- Integrate with init and bootstrap tools

## MCP Server Tool Design

### Handler Organization

#### 1. AdapterHandler
**Purpose**: Adapter discovery and configuration

**Tools**:
```python
@mcp.tool()
def list_adapters() -> dict:
    """List all available adapters with metadata"""

@mcp.tool()
def get_adapter_inputs(adapter_name: str) -> dict:
    """Get required inputs for adapter"""

@mcp.tool()
def validate_adapter_config(adapter_name: str, config: dict) -> dict:
    """Validate adapter configuration"""

@mcp.tool()
def get_adapter_metadata(adapter_name: str) -> dict:
    """Get adapter metadata (version, phase, capabilities)"""
```

#### 2. PlatformHandler
**Purpose**: Platform configuration management

**Tools**:
```python
@mcp.tool()
def generate_platform_yaml(adapters_config: dict) -> dict:
    """Generate platform.yaml from adapter configs"""

@mcp.tool()
def validate_platform_yaml(yaml_path: str) -> dict:
    """Validate platform.yaml structure"""

@mcp.tool()
def get_platform_status() -> dict:
    """Get current platform configuration status"""

@mcp.tool()
def merge_secrets(platform_yaml: str, secrets_file: str) -> dict:
    """Merge secrets from ~/.ztc/secrets into config"""
```

#### 3. RenderHandler
**Purpose**: Artifact generation and rendering

**Tools**:
```python
@mcp.tool()
def render_adapters(platform_yaml: str, partial: list = None) -> dict:
    """Render manifests for all or partial adapters"""

@mcp.tool()
def generate_pipeline_yaml(platform_yaml: str) -> dict:
    """Generate pipeline.yaml from adapter stages"""

@mcp.tool()
def generate_lock_file(platform_yaml: str, artifacts_hash: str) -> dict:
    """Generate lock file with hashes and metadata"""

@mcp.tool()
def extract_debug_scripts(platform_yaml: str) -> dict:
    """Extract scripts to debug directory"""
```

#### 4. BootstrapHandler
**Purpose**: Deployment execution

**Tools**:
```python
@mcp.tool()
def execute_stage(stage_name: str, context: dict, cache_enabled: bool = True) -> dict:
    """Execute single bootstrap stage with caching"""

@mcp.tool()
def get_stage_status(stage_name: str) -> dict:
    """Get execution status of stage"""

@mcp.tool()
def list_stages(pipeline_yaml: str) -> dict:
    """List all stages from pipeline.yaml"""

@mcp.tool()
def rollback_stage(stage_name: str) -> dict:
    """Rollback failed stage"""
```

#### 5. ValidationHandler
**Purpose**: Validation operations

**Tools**:
```python
@mcp.tool()
def validate_artifacts(lock_file: str) -> dict:
    """Validate artifacts against lock file"""

@mcp.tool()
def validate_runtime_dependencies() -> dict:
    """Check for required CLI tools (kubectl, talosctl, etc.)"""

@mcp.tool()
def validate_cluster_access(kubeconfig: str) -> dict:
    """Validate cluster connectivity"""
```

## CLI Command Refactoring

### Pattern: Orchestrator Commands

Each CLI command becomes a thin orchestrator that calls multiple MCP tools.

#### Example: `ztc init` Command

**Before** (Fat Client):
```python
def init():
    # Business logic in CLI
    registry = AdapterRegistry()
    for adapter in registry.list_adapters():
        inputs = adapter.get_required_inputs()
        config = collect_inputs(inputs)
    write_platform_yaml(config)
```

**After** (Thin Orchestrator):
```python
async def init():
    # Orchestrate MCP tool calls
    adapters = await mcp_client.call_tool("list_adapters")
    
    config = {}
    for adapter in adapters["adapters"]:
        inputs = await mcp_client.call_tool("get_adapter_inputs", 
                                           adapter_name=adapter["name"])
        adapter_config = await collect_inputs_interactive(inputs)
        config[adapter["name"]] = adapter_config
    
    result = await mcp_client.call_tool("generate_platform_yaml", 
                                       adapters_config=config)
    console.print(f"✓ Generated {result['path']}")
```

#### Example: `ztc render` Command

**After** (Thin Orchestrator):
```python
async def render(partial: list = None):
    # Validate platform.yaml exists
    validation = await mcp_client.call_tool("validate_platform_yaml", 
                                           yaml_path="platform.yaml")
    if not validation["valid"]:
        console.print(f"✗ {validation['error']}")
        return
    
    # Render adapters
    result = await mcp_client.call_tool("render_adapters", 
                                       platform_yaml="platform.yaml",
                                       partial=partial)
    
    # Generate pipeline.yaml
    pipeline = await mcp_client.call_tool("generate_pipeline_yaml",
                                         platform_yaml="platform.yaml")
    
    # Generate lock file
    lock = await mcp_client.call_tool("generate_lock_file",
                                     platform_yaml="platform.yaml",
                                     artifacts_hash=result["artifacts_hash"])
    
    console.print(f"✓ Rendered {result['adapter_count']} adapters")
    console.print(f"✓ Generated {pipeline['stage_count']} stages")
```

#### Example: `ztc bootstrap` Command

**After** (Thin Orchestrator):
```python
async def bootstrap(skip_cache: bool = False):
    # Validate lock file
    validation = await mcp_client.call_tool("validate_artifacts",
                                           lock_file="platform/lock.json")
    if not validation["valid"]:
        console.print(f"✗ {validation['error']}")
        return
    
    # Get stages
    stages_result = await mcp_client.call_tool("list_stages",
                                              pipeline_yaml="platform/generated/pipeline.yaml")
    
    # Execute stages with progress
    with Progress() as progress:
        task = progress.add_task("Bootstrap", total=len(stages_result["stages"]))
        
        for stage in stages_result["stages"]:
            result = await mcp_client.call_tool("execute_stage",
                                               stage_name=stage["name"],
                                               context=stage["context"],
                                               cache_enabled=not skip_cache)
            
            if result["status"] == "failed":
                console.print(f"✗ Stage {stage['name']} failed: {result['error']}")
                return
            
            progress.advance(task)
    
    console.print("✓ Bootstrap completed")
```

## File Structure Changes

### New Files to Create

```
libs/workflow_engine/
├── engine/
│   ├── resolver.py              # NEW - DependencyResolver
│   ├── bootstrap_executor.py    # NEW - BootstrapExecutor with caching
│   ├── pipeline_generator.py    # NEW - Pipeline YAML generation
│   └── script_executor.py       # NEW - Script execution with logging

libs/workflow_mcp/
├── handlers/
│   ├── __init__.py
│   ├── adapter_handler.py       # NEW - Adapter operations
│   ├── platform_handler.py      # NEW - Platform config operations
│   ├── render_handler.py        # NEW - Render operations
│   ├── bootstrap_handler.py     # NEW - Bootstrap operations
│   └── validation_handler.py    # NEW - Validation operations
└── workflow_server/
    └── mcp_server.py            # MODIFY - Register all handlers

libs/cli/
├── commands/
│   ├── init.py                  # REFACTOR - Thin orchestrator
│   ├── render.py                # REFACTOR - Thin orchestrator
│   ├── bootstrap.py             # REFACTOR - Thin orchestrator
│   └── validate.py              # REFACTOR - Thin orchestrator
└── mcp_client.py                # MODIFY - Add new tool calls
```

### Files to Modify

```
libs/workflow_mcp/workflow_server/mcp_server.py
- Import all handlers
- Register handlers with mcp instance
- Remove workflow-only limitation

libs/cli/mcp_client.py
- Add methods for new tools
- Add error handling for tool calls

libs/cli/commands/*.py
- Remove business logic
- Add MCP tool orchestration
- Keep only UI/UX logic
```

## Test Scenarios

### Test 1: CLI → MCP Server → Workflow Engine (Local E2E)

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

**Expected Flow**:
1. `ztc init` → calls `list_adapters`, `get_adapter_inputs`, `generate_platform_yaml`
2. `ztc render` → calls `validate_platform_yaml`, `render_adapters`, `generate_pipeline_yaml`, `generate_lock_file`
3. `ztc bootstrap` → calls `validate_artifacts`, `list_stages`, `execute_stage` (multiple times)
4. `ztc validate` → calls `validate_artifacts`, `validate_cluster_access`

**Success Criteria**:
- ✅ `platform.yaml` generated with all adapter configs
- ✅ `platform/generated/` contains manifests from all adapters
- ✅ `platform/generated/pipeline.yaml` contains all stages
- ✅ `platform/lock.json` generated with correct hashes
- ✅ Bootstrap executes all stages successfully
- ✅ Validation passes

### Test 2: IDE → MCP Server → Workflow Engine (Chat-Driven)

**Setup**:
```bash
# Terminal 1: Start MCP server
cd libs/workflow_mcp
python -m workflow_mcp.workflow_server.mcp_server --allow-write

# Terminal 2: Configure IDE (Claude Desktop)
# Add to ~/.config/claude/claude_desktop_config.json:
{
  "mcpServers": {
    "zerotouch": {
      "command": "python",
      "args": ["-m", "workflow_mcp.workflow_server.mcp_server", "--allow-write"],
      "cwd": "/path/to/zerotouch-engine/libs/workflow_mcp"
    }
  }
}
```

**Chat Interaction**:
```
User: "List available adapters"
AI: [calls list_adapters tool]
    "Available adapters: hetzner, cilium, talos, argocd, ksops..."

User: "Get inputs for hetzner adapter"
AI: [calls get_adapter_inputs tool with adapter_name="hetzner"]
    "Hetzner adapter requires: api_token, server_ips..."

User: "Generate platform.yaml with hetzner, cilium, and talos adapters"
AI: [calls get_adapter_inputs for each, collects configs, calls generate_platform_yaml]
    "Generated platform.yaml with 3 adapters"

User: "Render the platform"
AI: [calls render_adapters, generate_pipeline_yaml, generate_lock_file]
    "Rendered 3 adapters, generated 15 stages, created lock file"

User: "Execute bootstrap"
AI: [calls list_stages, then execute_stage for each stage]
    "Executing stage 1/15: Install Talos..."
    "Executing stage 2/15: Bootstrap Kubernetes..."
    ...
    "Bootstrap completed successfully"
```

**Success Criteria**:
- ✅ IDE can discover all MCP tools
- ✅ AI can call tools with correct parameters
- ✅ AI can orchestrate multi-step workflows
- ✅ Same artifacts generated as CLI test
- ✅ Bootstrap completes successfully

## Implementation Order

### Phase 1: Critical Gaps (Week 1)
1. **DependencyResolver** - Port from legacy (4 hours)
2. **BootstrapExecutor** - Create with caching (8 hours)
3. **PipelineGenerator** - Port from legacy (6 hours)
4. **ScriptExecutor** - Port from legacy (4 hours)

### Phase 2: MCP Handlers (Week 2)
5. **AdapterHandler** - Create with 4 tools (4 hours)
6. **PlatformHandler** - Create with 4 tools (4 hours)
7. **RenderHandler** - Create with 4 tools (6 hours)
8. **BootstrapHandler** - Create with 4 tools (6 hours)
9. **ValidationHandler** - Create with 3 tools (4 hours)

### Phase 3: CLI Refactoring (Week 3)
10. **Refactor init command** - Thin orchestrator (4 hours)
11. **Refactor render command** - Thin orchestrator (4 hours)
12. **Refactor bootstrap command** - Thin orchestrator (4 hours)
13. **Refactor validate command** - Thin orchestrator (2 hours)

### Phase 4: Testing (Week 4)
14. **Test 1: CLI E2E** - Manual testing (4 hours)
15. **Test 2: IDE Chat** - Manual testing (4 hours)
16. **Bug fixes and polish** - (8 hours)

**Total Estimated Effort**: 76 hours (~2 weeks with 2 developers)

## Success Metrics

1. **Zero business logic in CLI** - All logic in workflow_engine or MCP handlers
2. **All tools callable from IDE** - AI can orchestrate workflows
3. **Test 1 passes** - CLI → MCP → Engine works E2E
4. **Test 2 passes** - IDE → MCP → Engine works E2E
5. **Same artifacts as legacy** - Backward compatibility maintained

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| MCP tool granularity too fine | High latency for CLI | Batch operations where possible |
| State management complexity | Bugs in orchestration | Comprehensive logging and error handling |
| Breaking changes to existing workflows | User disruption | Maintain backward compatibility layer |
| Performance degradation | Slow CLI | Profile and optimize hot paths |

## Next Steps

1. Review and approve this spec
2. Create detailed implementation tasks
3. Assign tasks to developers
4. Begin Phase 1 implementation
5. Daily standups to track progress
6. Weekly demos of completed phases
