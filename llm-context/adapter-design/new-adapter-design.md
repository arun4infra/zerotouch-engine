# New ZTC Adapter — Design Spec

The design must clearly include the details below.

Design the implementation for a new ZTC Adapter in the following format.

---

## Requirements

### Source references
- Spec files must **clearly reference source files from the original ZTP project** so they can be reused.
- The only difference: original scripts pass args; migrated scripts use **context JSON** for inputs.
- Add the **source reference script at the top of each script**.

### Alignment with original
- New scripts must align patterns more closely with the original for consistency.
- Do **not** simplify the new scripts.

### Integration tests (ArgoCD pattern)
- Refer to **argocd/tests/** integration test cases for the pattern.
- Tests must use the **exact same** service classes, dependency injection, and business logic as production — this ensures maximum code coverage and validates actual production behavior.

Each adapter must have integration tests that:

1. Use `PlatformEngine(platform.yaml)`.
2. Call `await engine.render()`.
3. Verify files at `platform/generated/{adapter}/`.
4. Test actual manifest folders and their files for **all env**.
5. Validate the **generation of each file** the adapter is responsible for.

---

## Adapter — Design

### Template Files (in adapter)

### Template Sources (Reference Legacy ZTP)

### Scripts Sources (Reference Legacy ZTP)

### Render Output (`platform/generated/`)

**Generated Structure**

### Complete Lifecycle

### Key Understandings
