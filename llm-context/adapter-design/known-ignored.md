# Known Ignored Design Feedbacks

This document tracks design feedback that was evaluated and intentionally rejected, with rationale.

## Rejected Feedbacks

### 1. Native Sourcing vs Build-Time Inlining

**Feedback**: Use structured extraction to `lib/` folders with native Bash `source` statements instead of build-time text inlining via `# INCLUDE` markers.

**Rationale for Rejection**:
- Breaks portability: Scripts must be self-contained for air-gapped environments
- Violates Zero-Touch principle: `ztc eject` produces standalone artifacts, not directory trees with dependencies
- Talos adapter already uses build-time inlining successfully
- Relative path sourcing creates runtime dependencies on directory structure
- The "1:1 debugging" argument assumes scripts are modified post-ejection, which contradicts immutable artifact principle

**Status**: REJECTED - Keep build-time composition via `# INCLUDE` markers

---

### 2. YAML-Defined Scripts

**Feedback**: Define scripts in `adapter.yaml` instead of Python Enums to support dynamic/user-provided scripts.

**Rationale for Rejection**:
- Loses type safety: Python Enums provide compile-time validation via `ScriptReference.__post_init__`
- YAML approach defers validation to runtime
- Enum approach enables IDE autocomplete and refactoring tools
- YAML adds parsing overhead and loses static analysis benefits
- "Community Adapters" can still use Enums - they're just Python code

**Status**: REJECTED - Keep Enum-based script registry for type safety

---

### 3. Jinja2 Templates for Script Includes

**Feedback**: Use Jinja2 `{% include %}` directives instead of custom `# INCLUDE` markers for script composition.

**Rationale for Rejection**:
- Scripts are executable artifacts, not templates
- Jinja2 is for manifest/config generation (YAML), not bash scripts
- Adds unnecessary build complexity - requires template rendering at extraction time
- `# INCLUDE` markers are simple regex replacement during `get_embedded_script()`
- Talos adapter already uses `# INCLUDE` pattern successfully
- Both approaches have same line number preservation issues
- Violates separation of concerns: Jinja2 for data templating, not code composition

**Status**: REJECTED - Keep `# INCLUDE` markers for script composition
