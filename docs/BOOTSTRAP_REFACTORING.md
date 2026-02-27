# Bootstrap Pipeline Refactoring

## Overview

Refactored bootstrap pipeline execution to follow **separation of concerns** pattern, moving business logic from CLI to engine layer.

## Architecture Changes

### Before (CLI-Heavy):

```
CLI (bootstrap.py)
├─ Load config
├─ List stages
├─ FOR EACH stage:
│  ├─ Execute stage
│  ├─ Handle errors
│  └─ Display progress
└─ Show results
```

**Problem:** CLI contained business logic (iteration, error handling, flow control)

### After (Engine-Heavy):

```
CLI (bootstrap.py)
├─ Load config
├─ Define progress callback (display only)
└─ Call orchestrator.execute()

Engine (BootstrapOrchestrator)
├─ Generate pipeline if needed
├─ Load stages
├─ FOR EACH stage:
│  ├─ Execute stage
│  ├─ Handle errors
│  ├─ Track counters
│  └─ Call progress_callback()
└─ Return BootstrapResult
```

**Benefits:**
- ✅ CLI is thin presentation layer
- ✅ Engine contains all business logic
- ✅ Testable without CLI
- ✅ Reusable from other interfaces (API, MCP, etc.)

## Changes Made

### 1. Enhanced `BootstrapOrchestrator.execute()`

**File:** `libs/workflow_engine/src/workflow_engine/orchestration/bootstrap_orchestrator.py`

**Added:**
- `progress_callback` parameter for progress reporting
- Full stage iteration logic
- Error handling and early exit
- Counter tracking (executed, cached)
- Pipeline generation if missing

**Signature:**
```python
async def execute(
    self, 
    skip_cache: bool = False, 
    progress_callback=None
) -> BootstrapResult
```

**Progress Callback:**
```python
def callback(stage_name: str, status: str, message: str):
    """
    status: 'start' | 'success' | 'cached' | 'failed'
    message: Additional context (error message, description)
    """
```

### 2. Simplified CLI Bootstrap Command

**File:** `libs/cli/ztp_cli/commands/bootstrap.py`

**Removed:**
- Stage iteration loop
- Individual execute_stage() calls
- Error handling logic
- Counter tracking

**Kept:**
- Config validation
- Rich console display
- Progress visualization
- Result formatting

**New Flow:**
```python
# Define display callback
def progress_callback(stage_name, status, message):
    if status == 'start':
        progress.add_task(f"→ {stage_name}")
    elif status == 'success':
        console.print(f"✓ {stage_name}")
    # ... etc

# Execute (engine handles everything)
result = await orchestrator.execute(
    skip_cache=skip_cache,
    progress_callback=progress_callback
)

# Display final result
if result.success:
    console.print("✓ Bootstrap completed")
```

## Benefits

### 1. Separation of Concerns
- **CLI**: Presentation only (display, formatting, user interaction)
- **Engine**: Business logic (execution, error handling, flow control)
- **Executor**: Low-level operations (stage execution, cache, secrets)

### 2. Testability
```python
# Can test engine without CLI
orchestrator = BootstrapOrchestrator()
result = await orchestrator.execute()
assert result.success
assert result.stages_executed == 18
```

### 3. Reusability
```python
# Use from API
@app.post("/bootstrap")
async def bootstrap_api():
    orchestrator = BootstrapOrchestrator()
    result = await orchestrator.execute(
        progress_callback=lambda s, st, m: websocket.send(...)
    )
    return result

# Use from MCP
@mcp.tool()
async def bootstrap():
    orchestrator = BootstrapOrchestrator()
    result = await orchestrator.execute()
    return {"success": result.success}
```

### 4. Consistency with CDK Pattern

**AWS CDK:**
```typescript
// CLI
const app = new cdk.App();
app.synth();  // Engine does the work

// Engine
class App {
  synth() {
    // All synthesis logic here
  }
}
```

**ZTC (Now):**
```python
# CLI
orchestrator = BootstrapOrchestrator()
await orchestrator.execute()  # Engine does the work

# Engine
class BootstrapOrchestrator:
    async def execute(self):
        # All execution logic here
```

## Migration Guide

### For CLI Developers

**Before:**
```python
stages = orchestrator.list_stages()
for stage in stages:
    result = await orchestrator.execute_stage(stage['name'])
    if not result.success:
        print(f"Failed: {result.error}")
        return
```

**After:**
```python
def progress_callback(stage_name, status, message):
    print(f"{stage_name}: {status}")

result = await orchestrator.execute(progress_callback=progress_callback)
if not result.success:
    print(f"Failed at {result.failed_stage}: {result.error}")
```

### For Engine Developers

**New Responsibilities:**
- Pipeline generation (if missing)
- Stage iteration
- Error handling
- Progress reporting via callbacks

**Removed Responsibilities:**
- Display formatting (CLI's job)
- User interaction (CLI's job)

## Testing

### Unit Tests (Engine)
```python
async def test_bootstrap_success():
    orchestrator = BootstrapOrchestrator()
    result = await orchestrator.execute()
    assert result.success
    assert result.stages_executed > 0

async def test_bootstrap_failure():
    # Mock stage to fail
    result = await orchestrator.execute()
    assert not result.success
    assert result.failed_stage is not None
```

### Integration Tests (CLI)
```python
def test_cli_bootstrap():
    runner = CliRunner()
    result = runner.invoke(cli, ['bootstrap'])
    assert result.exit_code == 0
    assert "✓ Bootstrap completed" in result.output
```

## Future Enhancements

### 1. Parallel Execution
```python
# Engine can execute independent stages in parallel
async def execute(self, parallel: bool = False):
    if parallel:
        # Group stages by dependencies
        # Execute groups in parallel
```

### 2. Dry Run
```python
# Engine can simulate without executing
async def execute(self, dry_run: bool = False):
    if dry_run:
        # Validate but don't execute
```

### 3. Selective Execution
```python
# Engine can execute specific stages
async def execute(self, stages: List[str] = None):
    if stages:
        # Execute only specified stages
```

## Conclusion

This refactoring aligns ZTC with industry best practices (CDK pattern) and creates a clean separation between presentation and business logic. The engine is now the source of truth for execution logic, making it testable, reusable, and maintainable.
