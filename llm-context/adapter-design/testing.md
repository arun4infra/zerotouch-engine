## Testing Strategy

### Unit Tests
- Adapter configuration validation (Pydantic models)
- Capability contract enforcement
- Script reference validation

### Integration Tests
**Critical Principle: Same Code Paths as Production**
- Tests must use the exact same service classes, dependency injection, and business logic as production
- This ensures maximum code coverage and validates actual production behavior

### End-to-End Tests
- Full workflow (init → render → validate)
- Script extraction and execution (mocked)
- Lock file generation and validation

## Summary

The ZTC adapter pattern provides:
- **Modularity**: Adapters are independent, reusable units
- **Type Safety**: Pydantic models enforce contracts
- **Scalability**: Easy to add new adapters (19 planned)
- **Maintainability**: Clear separation of concerns
- **Compatibility**: Core logic preserved from zerotouch-platform
- **Safety**: Context files provide auditability and validation

The key innovation is replacing CLI arguments with JSON context files while preserving the battle-tested logic from the original zerotouch-platform scripts.


## Testing Strategy

### Unit Tests
- Adapter configuration validation (Pydantic models)
- Capability contract enforcement
- Script reference validation
- Script contract validation (META_REQUIRE headers)

### Integration Tests
- Adapter rendering with mocked APIs
- Capability data flow between adapters
- Context file generation and parsing
- Pre-flight health checks

### End-to-End Tests
- Full workflow (init → render → validate)
- Script extraction and execution (mocked)
- Lock file generation and validation
