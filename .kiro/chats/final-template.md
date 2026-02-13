Design the implementation for a new ZTC Adapter in below format.
the spec files must clealrly reference the source files from origional ztp project so that they can reuse.
only diff is that original script passes args and the migrated script will use context json for inputs.

- Tests must use the exact same service classes, dependency injection, and business logic as production
- This ensures maximum code coverage and validates actual production behavior
Do not include unit tests for the adapter. only include integration test.
accepentance crteia is validating the cli zommand by running "ztc render" and validating if all artifacts Output are genearted corretly at right places. running the test should run cli command "ztc render" and validate the generated output.
update the test case to use ztc render so that the test cases validate the files genearted.
integration test must do belw..
- Use "ztc render" to genearte the adapter files.
- Checks platform/generated/<adapter>/ directory
- Validates actual YAML files exist and contain expected content


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
