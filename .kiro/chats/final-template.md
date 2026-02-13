Design the implementation for a new ZTC Adapter in below format.
the spec files must clealrly reference the source files from origional ztp project so that they can reuse.
only diff is that original script passes args and the migrated script will use context json for inputs.

- Refer argocd/tests/ integration test cases for pattern.
- Tests must use the exact same service classes, dependency injection, and business logic as production
- This ensures maximum code coverage and validates actual production behavior

Each adapter needs integration tests following ArgoCD pattern:

Use PlatformEngine(platform.yaml)
Call await engine.render()
Verify files at platform/generated/{adapter}/
Test actual manifest folders and its files for all env
Test cases must validate the geneartion of each file the adapter is responsible for in test cases.

you should add the source reference script at top of each script.
The new scripts should align the patterns more closely with the original for consistency.
you should not simplify the new scripts.

## Adapter - Design


### Template Files (in adapter)


### Template Sources (Reference Legacy ZTP)


### Scripts Sources (Reference Legacy ZTP)

### Render Output (`platform/generated/`)
**Generated Structure**


### Complete Lifecycle


### Key Understandings
