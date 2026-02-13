# ZTC Adapter Design Pattern

## Overview

ZTC (ZeroTouch CLI) implements a capability-based adapter pattern for multi-cloud platform bootstrapping. Each adapter is a self-contained, independently deployable unit that provides specific infrastructure capabilities (cloud provider, OS, networking) while maintaining strict interface contracts.

## Core Design Principles

### 1. Adapter Independence
- **No Shared Dependencies**: Each adapter must be fully self-contained with no cross-adapter code dependencies
- **Adapter-Scoped Sharing**: Shared logic within an adapter lives in `scripts/shared/` folder
- **Build-Time Injection**: Helper functions injected during script extraction via `# INCLUDE:` markers
- **Runtime Independence**: Extracted scripts remain self-contained with no external file dependencies
- **Isolated Execution**: Adapters can be developed, tested, and deployed independently

### 2. Capability-Based Architecture
- **Explicit Contracts**: Adapters declare capabilities they provide and require via Pydantic models
- **Type Safety**: All capability data is validated against schemas at runtime
- **Dependency Resolution**: Engine automatically orders adapter execution based on capability dependencies

### 3. Declarative Configuration
- **Platform.yaml**: Single source of truth for platform configuration
- **Version Pinning**: All component versions explicitly declared and locked
- **Immutable Artifacts**: Generated manifests are hashed and validated against lock file

### 4. Script Extraction with Context Files
- **Core Logic Preservation**: Original script logic remains unchanged
- **Context Over Arguments**: Scripts read JSON context files instead of CLI arguments
- **Backward Compatibility**: Extracted scripts maintain same behavior as originals