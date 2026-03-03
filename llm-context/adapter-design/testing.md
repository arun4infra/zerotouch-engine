## Testing Strategy

### Unit Tests
- No Unit tests to be written.

### Integration Tests
**Critical Principle: Same Code Paths as Production**
- Tests must use the exact same service classes, dependency injection, and business logic as production
- This ensures maximum code coverage and validates actual production behavior
- Tests must not hold any core or business logics in it. It should hold testing and asserting logics. Production flow should not require re-implementation of logics from test case.

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

### Integration Tests
- Adapter rendering with real APIs
- Capability data flow between adapters
- Context file generation and parsing
- Pre-flight health checks
- Test cases must never be skipped
- Tests uses age key provider to decrypt the keys in secrets. secrets will never be exported. The secrets are decrypted at runtime using the Age key provider and SOPS.