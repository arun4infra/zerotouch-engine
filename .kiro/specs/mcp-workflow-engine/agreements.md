# Summary: MCP-Based Workflow Engine API

## Core Design

**Backend Service**: Python FastAPI exposing MCP protocol for workflow orchestration

**Purpose**: Centralize workflow decision logic, enable dynamic flow changes without CLI redeployment

## Key Components

### 1. Workflow Engine
- Loads declarative workflow definitions (YAML)
- Manages session state (in-memory/PostgreSQL)
- Evaluates conditional transitions based on user answers
- Activates adapters based on workflow state

### 2. MCP Protocol Layer
- Exposes workflow operations as MCP tools/resources
- CLI communicates via MCP JSON-RPC (stdio or HTTP)
- Stateful conversation model (session-based)

### 3. Adapter Integration
- Reuses existing zerotouch-engine adapters (Hetzner, ArgoCD, etc.)
- Adapters provide questions via `get_required_inputs()`
- Backend orchestrates which adapters to prompt based on workflow state

## API Operations (MCP Tools)

1. `workflow/start` - Initialize session, return first question
2. `workflow/answer` - Submit answer, get next question + validation
3. `workflow/state` - Get current progress, completed answers
4. `workflow/complete` - Finalize, return platform.yaml + adapter configs

## Workflow Definition Format

Declarative YAML with states, transitions, adapter activation rules (similar to GitHub Actions/Argo)

## Benefits Achieved

- Hot-reload workflows without CLI changes
- Complex branching (your diagram's 6+ paths)
- Centralized validation and business rules
- Reuse existing Python adapter ecosystem

**Ready to proceed with spec creation?**


# React Question Path Engine - Applicable Patterns

## Core Pattern: **Traverser with Observer + State Restoration**

This engine implements a **stateful question flow traverser** with powerful patterns directly applicable to your workflow:

### 1. **QuestionPathTraverser Pattern** (Primary)
- **Stateful navigation** through question tree with level tracking (stack-based)
- **Automatic answer handling** - skips questions with pre-determined answers
- **Restore/Rewind capability** - resume from any point in the flow
- **Observer notifications** - decoupled event handling for UI updates

### 2. **Feedback System** (Critical for MCP)
- Each answer creates a `QuestionPathFeedback` object with:
  - Unique ID, timestamp, question, answer, planning context
  - Enables undo/redo, audit trail, session persistence
- **Proposal mechanism** - pre-populate answers for review before commit

### 3. **Level Stack Navigation**
- Handles nested question paths (your diagram's sub-flows)
- Jump to child question path, return to parent after completion
- Maintains context per level (planning context = adapter config)

### 4. **Automatic Answer Provider Interface**
- Equivalent to cb-engine's `derive_field_value()` + `should_skip_field()`
- Enables conditional skipping and auto-population

## Recommended Adoption for Zerotouch

**Use this pattern for MCP workflow API**:
- `QuestionPathTraverser` → `WorkflowSessionManager`
- `QuestionPathFeedback` → `WorkflowAnswer` (persisted for session restore)
- `PlanningContext` → `AdapterActivationContext`
- Observer pattern → MCP notification events

**Key advantage**: Battle-tested in production (TX-Flex), handles complex branching, built-in undo/restore.

---------

# Correct - No DB Required

**Your understanding is correct.**

## QuestionPathTraverser Pattern - Stateless Service

The pattern is **in-memory state management** with optional persistence:

### Core Architecture
- **Service holds session state in memory** (Python dict/objects)
- **Feedback array** = list of answers in current session
- **Level stack** = navigation history (which question paths visited)
- **No database dependency** for core functionality

### Persistence is Optional
- **Session restore** requires serializing feedback array (JSON)
- **Storage options**: File system, Redis, DB, or **client-side** (CLI stores state locally)
- Pattern works **without any persistence** - session lives only during API connection

### For MCP Protocol
- **Stateful MCP server** - holds session in memory during conversation
- **Client reconnection** - CLI sends previous feedback array to restore state
- **No DB needed** - unless you want multi-user sessions or audit logging

### Comparison
- **React engine**: In-memory only (browser state)
- **Your workflow API**: Same - in-memory Python service
- **Optional**: Add PostgreSQL later for session history/analytics

Pattern is **pure state machine** - DB is orthogonal concern.

--------

# Correct - No DB Required

**Your understanding is correct.**

## QuestionPathTraverser Pattern - Stateless Service

The pattern is **in-memory state management** with optional persistence:

### Core Architecture
- **Service holds session state in memory** (Python dict/objects)
- **Feedback array** = list of answers in current session
- **Level stack** = navigation history (which question paths visited)
- **No database dependency** for core functionality

### Persistence is Optional
- **Session restore** requires serializing feedback array (JSON)
- **Storage options**: File system, Redis, DB, or **client-side** (CLI stores state locally)
- Pattern works **without any persistence** - session lives only during API connection

### For MCP Protocol
- **Stateful MCP server** - holds session in memory during conversation
- **Client reconnection** - CLI sends previous feedback array to restore state
- **No DB needed** - unless you want multi-user sessions or audit logging

### Comparison
- **React engine**: In-memory only (browser state)
- **Your workflow API**: Same - in-memory Python service
- **Optional**: Add PostgreSQL later for session history/analytics

Pattern is **pure state machine** - DB is orthogonal concern.

-----------

# Plan Assessment - Agreed with Refinement

## Your Phased Approach is Sound

**Phase 1** (Iteration 1):
1. ✅ CLI + Filesystem state (`.ztc/session.json`)
2. ✅ MCP conversational state (in-memory during session)

**Phase 2** (Future):
3. ✅ PostgreSQL for multi-session persistence

## Design Recommendation: **Strategy Pattern for Storage**

Implement **SessionStore interface** from day one:

```python
class SessionStore(ABC):
    @abstractmethod
    def save(session_id, feedback_array) → None
    def load(session_id) → feedback_array

# Phase 1 implementations
class FilesystemStore(SessionStore)  # CLI use case
class InMemoryStore(SessionStore)     # MCP conversation use case

# Phase 2 implementation  
class PostgresStore(SessionStore)     # Multi-session persistence
```

## Critical Design Decision

**MCP conversational state** - clarify:
- **Option A**: State lives in MCP server memory (lost on server restart)
- **Option B**: State serialized in MCP conversation context (client holds it)

**Recommendation**: Option B - MCP client (CLI) holds serialized state, sends with each request. Server remains stateless. Aligns with MCP's design philosophy.

## Agreed - proceed with Phase 1 spec focusing on filesystem + in-memory stores.

--------