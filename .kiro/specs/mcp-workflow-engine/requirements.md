# Requirements Document: MCP Workflow Engine

## Introduction

The MCP Workflow Engine is a Python-based backend service that orchestrates conditional question flows for infrastructure provisioning workflows. It exposes the Model Context Protocol (MCP) for client communication and manages complex branching workflows with state management. The engine reuses existing zerotouch-engine adapters (Hetzner, ArgoCD, etc.) and supports session persistence, automatic answer handling, and workflow state restoration.

## Glossary

- **MCP_Server**: The Python backend service exposing MCP protocol endpoints for workflow orchestration
- **CLI_Client**: Command-line interface client that communicates with MCP_Server via JSON-RPC
- **Workflow_Engine**: Core orchestration component managing question flows and state transitions
- **QuestionPathTraverser**: Stateful navigation component tracking current position in workflow tree with level tracking
- **SessionStore**: Interface for persisting and retrieving workflow session state
- **FilesystemStore**: SessionStore implementation using `.ztc/session.json` for persistence
- **InMemoryStore**: SessionStore implementation for testing without filesystem dependencies
- **Feedback_Object**: Immutable record of user answer with ID, timestamp, and context
- **Workflow_DSL**: YAML-based declarative workflow definition format
- **PlatformAdapter**: Base class from zerotouch-engine for infrastructure provider integrations
- **AdapterRegistry**: Component for discovering and loading available adapters
- **PlatformContext**: Configuration container for adapter initialization

## Requirements

### Requirement 1: QuestionPathTraverser Pattern Implementation

**User Story:** As a developer, I want the workflow navigation to use the QuestionPathTraverser pattern, so that state management follows proven architectural patterns with level tracking.

#### Acceptance Criteria

1. THE Workflow_Engine SHALL implement QuestionPathTraverser pattern with stateful navigation
2. WHEN traversing workflow nodes, THE QuestionPathTraverser SHALL maintain current level tracking
3. WHEN moving between questions, THE QuestionPathTraverser SHALL update internal state with position information
4. THE QuestionPathTraverser SHALL expose methods for forward navigation, backward navigation, and position queries
5. WHEN serializing state, THE QuestionPathTraverser SHALL include level and position metadata

### Requirement 2: Strategy Pattern for Session Storage

**User Story:** As a developer, I want pluggable session storage implementations, so that I can switch between filesystem and in-memory storage without changing core logic.

#### Acceptance Criteria

1. THE SessionStore interface SHALL define save, load, and delete operations for session persistence
2. THE CLI_Client SHALL implement FilesystemStore conforming to SessionStore interface
3. THE MCP_Server SHALL implement InMemoryStore conforming to SessionStore interface for testing
4. THE FilesystemStore SHALL be CLIENT-SIDE component where CLI_Client persists session data to `.ztc/session.json` with atomic writes
5. THE InMemoryStore SHALL maintain session data in memory without filesystem access
6. THE MCP_Server SHALL NOT persist session state to disk, relying on client-provided state in each request

### Requirement 3: Observer Pattern for Workflow Events

**User Story:** As a developer, I want event notifications for workflow state changes, so that I can implement logging, monitoring, and debugging capabilities.

#### Acceptance Criteria

1. THE Workflow_Engine SHALL implement Observer pattern for state change notifications
2. WHEN workflow state changes, THE Workflow_Engine SHALL notify all registered observers
3. THE Workflow_Engine SHALL support observer registration and deregistration
4. WHEN answer is submitted, THE Workflow_Engine SHALL emit answer_submitted event
5. WHEN question is presented, THE Workflow_Engine SHALL emit question_presented event
6. WHEN workflow completes, THE Workflow_Engine SHALL emit workflow_completed event
7. WHEN session is restored, THE Workflow_Engine SHALL emit session_restored event
8. THE MCP_Server SHALL deliver workflow events via MCP notification protocol using send_notification() method to connected clients

### Requirement 4: Immutable Feedback System

**User Story:** As a user, I want each answer to create an immutable feedback record, so that I can review my answer history and support undo/redo operations.

#### Acceptance Criteria

1. WHEN user submits answer, THE Workflow_Engine SHALL create Feedback_Object with unique ID
2. THE Feedback_Object SHALL include timestamp of answer submission
3. THE Feedback_Object SHALL include question context (question ID, question text, question type)
4. THE Feedback_Object SHALL include answer value and validation status
5. THE Feedback_Object SHALL be immutable after creation
6. THE Workflow_Engine SHALL maintain ordered list of Feedback_Object instances
7. WHEN serializing session, THE Workflow_Engine SHALL include complete feedback history

### Requirement 5: Declarative Workflow DSL

**User Story:** As a workflow designer, I want to define workflows in YAML format, so that I can create and modify workflows without changing code.

#### Acceptance Criteria

1. THE MCP_Server SHALL parse Workflow_DSL from YAML files
2. THE MCP_Server SHALL use Pydantic for YAML schema validation
3. THE Workflow_DSL SHALL support state definitions with unique identifiers
4. THE Workflow_DSL SHALL support transition definitions with conditions
5. THE Workflow_DSL SHALL support question definitions with type, prompt, and validation rules
6. WHEN loading workflow, THE MCP_Server SHALL validate Workflow_DSL against schema
7. WHEN Workflow_DSL is invalid, THE MCP_Server SHALL return descriptive error with line number
8. THE Workflow_DSL SHALL support conditional branching based on previous answers
9. THE Workflow_DSL SHALL support automatic answer handling for pre-determined values

### Requirement 6: MCP Protocol Communication

**User Story:** As a CLI user, I want to communicate with the workflow engine via MCP protocol, so that I can use standard tooling and maintain stateless server architecture.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose workflow operations as MCP tools over stdio transport
2. WHEN CLI_Client sends tool call request, THE MCP_Server SHALL parse MCP protocol message
3. WHEN MCP_Server processes tool call, THE system SHALL return CallToolResult response
4. THE MCP_Server SHALL support HTTP transport as alternative to stdio
5. WHEN transport error occurs, THE MCP_Server SHALL return JSON-RPC error response with code and message
6. THE MCP_Server SHALL remain stateless between requests
7. WHEN session state is needed, THE CLI_Client SHALL include serialized state in tool call parameters

### Requirement 7: Session Management Operations

**User Story:** As a user, I want to start and restore workflow sessions, so that I can resume interrupted workflows.

#### Acceptance Criteria

1. WHEN user starts workflow, THE MCP_Server SHALL create new session with unique ID
2. WHEN user starts workflow, THE MCP_Server SHALL return first question, session ID, and serialized state blob from Workflow_DSL
3. WHEN user submits answer, THE MCP_Server SHALL validate answer against question rules
4. WHEN answer is valid, THE MCP_Server SHALL update session state and return next question
5. WHEN answer is invalid, THE MCP_Server SHALL return validation error without state change
6. WHEN user requests session restore, THE MCP_Server SHALL reconstruct workflow state from provided state blob
7. WHEN user restarts workflow, THE workflow SHALL always begin from first question regardless of previous session state

### Requirement 8: Automatic Answer Handling

**User Story:** As a workflow designer, I want to skip questions with pre-determined answers, so that users don't answer questions with obvious values.

#### Acceptance Criteria

1. WHEN question has automatic answer defined, THE Workflow_Engine SHALL skip question presentation
2. WHEN automatic answer is applied, THE Workflow_Engine SHALL create Feedback_Object with auto-answer flag
3. WHEN automatic answer is applied, THE Workflow_Engine SHALL proceed to next question
4. THE Workflow_DSL SHALL support automatic answer expressions referencing previous answers
5. WHEN automatic answer expression fails, THE Workflow_Engine SHALL present question to user

### Requirement 9: Adapter Integration

**User Story:** As a workflow designer, I want to activate adapters based on workflow state, so that infrastructure provisioning happens at correct workflow stages.

#### Acceptance Criteria

1. THE MCP_Server SHALL integrate with existing AdapterRegistry
2. WHEN workflow state requires adapter, THE Workflow_Engine SHALL load adapter from AdapterRegistry
3. WHEN activating adapter, THE Workflow_Engine SHALL construct PlatformContext from session answers
4. WHEN adapter requires inputs, THE Workflow_Engine SHALL map workflow answers to adapter input prompts
5. THE Workflow_Engine SHALL support cross-adapter dependencies where adapters access answers from other adapters
6. WHEN constructing PlatformContext, THE Workflow_Engine SHALL merge answers from multiple adapters
7. THE Workflow_Engine SHALL reuse existing PlatformAdapter base class without modification
8. WHEN adapter execution fails, THE Workflow_Engine SHALL return error without state change
9. THE Workflow_Engine SHALL support dynamic adapter choices via `get_dynamic_choices()` method for runtime API calls (e.g., AWS VPCs, Hetzner servers)
10. THE Adapters SHALL be restricted to read-only operations (validation, data fetching) during workflow traversal, state-mutating operations (resource creation, deletion) are prohibited until workflow completion phase or external execution
11. THE Workflow_Engine SHALL provide translation layer converting PlatformAdapter InputPrompt objects to Workflow_DSL question nodes with automatic field mapping

### Requirement 10: Session Restart

**User Story:** As a user, I want to restart workflows from the beginning, so that I can correct mistakes by starting fresh.

#### Acceptance Criteria

1. WHEN user requests workflow restart, THE Workflow_Engine SHALL discard current session state
2. WHEN workflow restarts, THE Workflow_Engine SHALL present first question from Workflow_DSL
3. WHEN workflow restarts, THE Workflow_Engine SHALL generate new session ID
4. THE Workflow_Engine SHALL NOT support partial rewind or undo operations within active sessions

### Requirement 11: Answer Validation

**User Story:** As a workflow designer, I want to validate user answers against rules, so that invalid data doesn't propagate through the workflow.

#### Acceptance Criteria

1. THE Workflow_DSL SHALL support validation rules for string, integer, boolean, and choice question types
2. WHEN answer is submitted, THE Workflow_Engine SHALL validate against question type
3. WHEN answer is submitted, THE Workflow_Engine SHALL validate against custom validation rules
4. WHEN validation fails, THE Workflow_Engine SHALL return error message from validation rule
5. THE Workflow_DSL SHALL support regex validation for string answers
6. THE Workflow_DSL SHALL support range validation for integer answers
7. THE Workflow_DSL SHALL support enum validation for choice answers
8. THE Workflow_DSL SHALL support cross-field validation rules referencing multiple answers

### Requirement 12: Session Serialization

**User Story:** As a developer, I want session state to be JSON-serializable, so that CLI_Client can hold state and MCP_Server remains stateless.

#### Acceptance Criteria

1. WHEN serializing session, THE Workflow_Engine SHALL produce JSON-compatible dictionary
2. THE serialized session SHALL include session ID, workflow ID, and current question ID
3. THE serialized session SHALL include complete feedback history
4. THE serialized session SHALL include QuestionPathTraverser state with level tracking
5. WHEN deserializing session, THE Workflow_Engine SHALL reconstruct identical state
6. WHEN deserializing session, THE Workflow_Engine SHALL validate session schema
7. WHEN deserialization fails, THE Workflow_Engine SHALL return descriptive error
8. THE serialized session SHALL include workflow DSL schema version hash for version mismatch detection

### Requirement 13: Nested Workflow Navigation

**User Story:** As a workflow designer, I want to define nested question paths, so that complex workflows can be decomposed into reusable sub-flows.

#### Acceptance Criteria

1. THE Workflow_DSL SHALL support nested workflow definitions with parent-child relationships
2. WHEN workflow transitions to child workflow, THE QuestionPathTraverser SHALL push current level to stack
3. WHEN child workflow completes, THE QuestionPathTraverser SHALL pop level from stack and resume parent
4. THE QuestionPathTraverser SHALL maintain separate context for each workflow level
5. WHEN serializing session, THE Workflow_Engine SHALL include complete level stack state
6. WHEN child workflow is entered, THE Workflow_Engine SHALL inherit parent context
7. WHEN child workflow modifies context, THE changes SHALL be visible to parent after return
8. THE Workflow_DSL SHALL support conditional child workflow loading based on previous answers

### Requirement 14: Deferred Workflow Operations

**User Story:** As a workflow designer, I want to register operations that execute on workflow completion, so that final artifacts are generated only after all answers collected.

#### Acceptance Criteria

1. THE Workflow_Engine SHALL support registration of deferred operations during workflow traversal
2. WHEN workflow completes successfully, THE Workflow_Engine SHALL execute all registered operations in order
3. WHEN workflow is canceled, THE Workflow_Engine SHALL discard all registered operations without execution
4. THE deferred operations SHALL have access to complete feedback history
5. THE deferred operations SHALL have access to final PlatformContext
6. WHEN deferred operation fails, THE Workflow_Engine SHALL return error with operation details
7. THE Workflow_Engine SHALL support rollback of deferred operations on failure
8. WHEN serializing session, THE Workflow_Engine SHALL include registered deferred operations

### Requirement 15: Session Restoration

**User Story:** As a user, I want to restore interrupted workflow sessions, so that I can continue from where I left off.

#### Acceptance Criteria

1. WHEN restoring session, THE Workflow_Engine SHALL reconstruct state from serialized state blob
2. WHEN presenting restored question, THE Workflow_Engine SHALL include previously submitted answer as default value
3. WHEN user accepts default answer, THE Workflow_Engine SHALL proceed to next question
4. WHEN user modifies answer, THE Workflow_Engine SHALL update feedback history and proceed
5. THE Workflow_Engine SHALL NOT support partial answer proposals or speculative answer chains
6. WHEN serializing session, THE Workflow_Engine SHALL include only committed feedback history

### Requirement 16: Secrets Management

**User Story:** As a workflow designer, I want to handle sensitive fields securely, so that secrets are never serialized or logged in plaintext.

#### Acceptance Criteria

1. THE Workflow_DSL SHALL support marking question fields as sensitive with `sensitive: true` flag
2. WHEN question is marked sensitive, THE Workflow_Engine SHALL use reference-based approach storing environment variable names
3. WHEN serializing session, THE Workflow_Engine SHALL store environment variable reference (e.g., `$HETZNER_API_TOKEN`) instead of actual secret value
4. WHEN deserializing session, THE Workflow_Engine SHALL resolve environment variable references to actual values at runtime
5. WHEN constructing PlatformContext, THE Workflow_Engine SHALL resolve secret references before passing to adapters
6. WHEN logging or emitting events, THE Workflow_Engine SHALL redact sensitive field values
7. THE Feedback_Object SHALL mark sensitive answers with `is_sensitive: true` flag
8. WHEN displaying feedback history, THE CLI_Client SHALL mask sensitive values with `***REDACTED***`
9. WHEN deferred operations access sensitive fields, THE values SHALL be resolved from environment at execution time

### Requirement 17: Transport Security Strategies

**User Story:** As a platform operator, I want configurable transport security modes, so that development workflows remain simple while production deployments enforce encryption.

#### Acceptance Criteria

1. THE MCP_Server SHALL support Development Mode where HTTP transport is permitted on localhost interfaces only
2. THE MCP_Server SHALL support Production Mode where HTTPS/TLS is mandatory for all network communication
3. WHEN in Production Mode, THE MCP_Server SHALL reject non-TLS connections
4. THE CLI_Client SHALL verify TLS certificates by default when connecting in Production Mode
5. THE MCP_Server SHALL support stdio transport for local CLI usage, which implies secure in-memory communication without TLS
