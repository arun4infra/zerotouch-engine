# Implementation Plan: MCP Workflow Engine

## Overview

This implementation plan follows a user journey approach, building the MCP Workflow Engine incrementally from core workflow traversal through adapter integration. Each phase includes checkpoint validation with concrete test scripts that verify real behavior using actual service classes. The implementation uses Python with Hypothesis for property-based testing and integrates with existing zerotouch-engine adapters.

## Tasks

- [ ] 1. Set up project structure and core data models
  - Create `ztc/mcp_workflow_engine/` directory structure
  - Implement core data models: `Entry`, `EntryData`, `QuestionNode`, `ValidationRules`, `WorkflowDSL`
  - Implement `QuestionPathFeedback` as frozen dataclass with serialization methods
  - Implement `QuestionPathLevelTracker` with state tracking fields
  - Set up Pydantic models for workflow DSL validation
  - Configure Hypothesis for property-based testing
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.2, 5.3, 5.4, 5.5, 12.2, 12.3, 12.4_

- [ ]* 1.1 Write property test for feedback object immutability
  - **Property 5: Feedback object uniqueness and immutability**
  - **Validates: Requirements 4.1, 4.5**

- [ ]* 1.2 Write property test for feedback object completeness
  - **Property 6: Feedback object completeness**
  - **Validates: Requirements 4.2, 4.3, 4.4**

- [ ]* 1.3 Write property test for workflow DSL state ID uniqueness
  - **Property 8: Workflow DSL state ID uniqueness**
  - **Validates: Requirements 5.3**

- [ ] 2. Implement QuestionPathTraverser core navigation
  - Implement `QuestionPathTraverser` class with initialization
  - Implement `start_async()` method for workflow initialization
  - Implement `get_current_question()` method
  - Implement `answer_current_question_async()` method with state updates
  - Implement feedback history management with monotonic ID generation
  - Implement level tracking with `current_level` and `level_stack`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.6, 4.7_

- [ ]* 2.1 Write property test for traverser state consistency
  - **Property 1: Traverser state consistency during navigation**
  - **Validates: Requirements 1.2, 1.3**

- [ ]* 2.2 Write property test for feedback history ordering
  - **Property 7: Feedback history ordering**
  - **Validates: Requirements 4.6**

- [ ] 3. Checkpoint: Core traversal validation
  - **Deliverables**: QuestionPathTraverser with basic navigation, feedback history, level tracking
  - **Verification**: Run integration test script that creates a simple 3-question workflow, answers all questions, verifies feedback history order and completeness
  - **Test Script**: `tests/checkpoints/test_checkpoint_1_core_traversal.py`
  - Ensure all tests pass, ask the user if questions arise

- [ ] 4. Implement session serialization and restoration
  - Implement `serialize()` method on QuestionPathTraverser
  - Implement `restore_async()` method with state reconstruction
  - Implement serialization for QuestionPathFeedback with `to_dict()` and `from_dict()`
  - Implement serialization for QuestionPathLevelTracker
  - Add workflow DSL version hash to serialized state
  - Implement session schema validation on deserialization
  - _Requirements: 1.5, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8_

- [ ]* 4.1 Write property test for session state round-trip preservation
  - **Property 2: Session state round-trip preservation**
  - **Validates: Requirements 1.5, 4.7, 7.6, 12.1, 12.2, 12.3, 12.4, 12.5, 13.5, 14.8, 15.1**

- [ ]* 4.2 Write property test for session restoration default answers
  - **Property 27: Session restoration default answers**
  - **Validates: Requirements 15.2, 15.3**

- [ ]* 4.3 Write property test for session restoration answer modification
  - **Property 28: Session restoration answer modification**
  - **Validates: Requirements 15.4**

- [ ]* 4.4 Write property test for committed feedback only
  - **Property 29: Session restoration committed feedback only**
  - **Validates: Requirements 15.6**

- [ ] 5. Implement SessionStore strategy pattern
  - Create `SessionStore` abstract base class with save/load/delete methods
  - Implement `FilesystemStore` with atomic writes to `.ztc/session.json`
  - Implement `InMemoryStore` for testing
  - Add error handling for file operations
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [ ]* 5.1 Write property test for filesystem atomic write safety
  - **Property 3: Filesystem atomic write safety**
  - **Validates: Requirements 2.4**

- [ ] 6. Checkpoint: Session persistence validation
  - **Deliverables**: Complete session serialization, FilesystemStore with atomic writes, session restoration
  - **Verification**: Run integration test that starts workflow, answers 2 questions, saves to filesystem, kills process, restores from filesystem, verifies state matches
  - **Test Script**: `tests/checkpoints/test_checkpoint_2_session_persistence.py`
  - Ensure all tests pass, ask the user if questions arise

- [ ] 7. Implement Observer pattern for workflow events
  - Create `QuestionPathTraverserObserver` abstract base class
  - Implement observer registration and deregistration in QuestionPathTraverser
  - Implement event notification classes: `QuestionPathNextQuestionReady`, `QuestionPathFeedbackEntered`, `QuestionPathFeedbackUpdated`, `QuestionPathCompleted`, `SessionRestored`
  - Emit notifications on state changes (answer submission, question presentation, completion, restoration)
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [ ]* 7.1 Write property test for observer notification completeness
  - **Property 4: Observer notification completeness**
  - **Validates: Requirements 3.2, 3.4, 3.5, 3.6, 3.7**

- [ ] 8. Implement Workflow DSL parser with Pydantic
  - Create `WorkflowDSLParser` class
  - Implement `parse_yaml()` method with PyYAML
  - Add Pydantic schema validation for WorkflowDSL
  - Implement line number extraction for validation errors using ruamel.yaml
  - Add support for conditional branching and automatic answers in DSL
  - _Requirements: 5.1, 5.2, 5.6, 5.7, 5.8, 5.9_

- [ ]* 8.1 Write property test for workflow DSL validation correctness
  - **Property 9: Workflow DSL validation correctness**
  - **Validates: Requirements 5.6, 5.7**

- [ ] 9. Implement answer validation system
  - Create validation rule classes for string, integer, boolean, choice types
  - Implement regex validation for strings
  - Implement range validation for integers
  - Implement enum validation for choices
  - Implement cross-field validation with expression evaluator
  - Add validation error messages with field context
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8_

- [ ]* 9.1 Write property test for answer validation state preservation
  - **Property 13: Answer validation state preservation**
  - **Validates: Requirements 7.3, 7.4, 7.5, 11.2, 11.3, 11.4**

- [ ] 10. Checkpoint: Workflow DSL and validation
  - **Deliverables**: Complete workflow DSL parser, answer validation system, observer notifications
  - **Verification**: Run integration test that loads complex workflow YAML with nested states, conditional transitions, validation rules; submit valid and invalid answers; verify validation errors and state preservation
  - **Test Script**: `tests/checkpoints/test_checkpoint_3_dsl_validation.py`
  - Ensure all tests pass, ask the user if questions arise

- [ ] 11. Implement automatic answer provider
  - Create `AutomaticAnswerProvider` class
  - Implement expression evaluator for automatic answer expressions
  - Implement `get_automatic_answer_async()` method
  - Integrate with QuestionPathTraverser to skip auto-answered questions
  - Create Feedback_Object with auto-answer flag for skipped questions
  - Add fallback to manual input when expression fails
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ]* 11.1 Write property test for automatic answer skipping
  - **Property 15: Automatic answer skipping**
  - **Validates: Requirements 8.1, 8.2, 8.3**

- [ ]* 11.2 Write property test for automatic answer fallback
  - **Property 16: Automatic answer fallback**
  - **Validates: Requirements 8.5**

- [ ] 12. Implement nested workflow navigation
  - Add level stack push/pop operations to QuestionPathTraverser
  - Implement child workflow entry with context inheritance
  - Implement child workflow completion with parent resumption
  - Add level stack serialization to session state
  - Implement conditional child workflow loading
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8_

- [ ]* 12.1 Write property test for nested workflow level stack consistency
  - **Property 22: Nested workflow level stack consistency**
  - **Validates: Requirements 13.2, 13.3**

- [ ]* 12.2 Write property test for nested workflow context isolation
  - **Property 23: Nested workflow context isolation and inheritance**
  - **Validates: Requirements 13.4, 13.6, 13.7**

- [ ] 13. Checkpoint: Advanced workflow features
  - **Deliverables**: Automatic answer provider, nested workflow navigation with level stack
  - **Verification**: Run integration test with workflow containing auto-answered questions and nested sub-workflows; verify questions are skipped, feedback has auto-answer flag, level stack grows/shrinks correctly, context inheritance works
  - **Test Script**: `tests/checkpoints/test_checkpoint_4_advanced_features.py`
  - Ensure all tests pass, ask the user if questions arise

- [ ] 14. Implement deferred operations registry
  - Create `OnQuestionPathCompleteOperation` abstract base class
  - Create `DeferredOperationsRegistry` class
  - Implement operation registration during traversal
  - Implement `execute_all()` method for workflow completion
  - Implement `rollback_all()` method for failure handling
  - Add deferred operations to session serialization
  - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8_

- [ ]* 14.1 Write property test for deferred operations execution order
  - **Property 24: Deferred operations execution order**
  - **Validates: Requirements 14.2, 14.4, 14.5**

- [ ]* 14.2 Write property test for deferred operations cancellation
  - **Property 25: Deferred operations cancellation**
  - **Validates: Requirements 14.3**

- [ ]* 14.3 Write property test for deferred operations rollback
  - **Property 26: Deferred operations rollback**
  - **Validates: Requirements 14.6, 14.7**

- [ ] 15. Implement secrets management system
  - Add `sensitive` flag to QuestionNode model
  - Implement environment variable reference storage in serialization
  - Create `SecretResolver` class for runtime resolution
  - Implement secret redaction in logging and events
  - Add `is_sensitive` flag to QuestionPathFeedback
  - Implement secret resolution in PlatformContext construction
  - Implement deferred secret resolution for operations
  - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 16.8, 16.9_

- [ ]* 15.1 Write property test for sensitive field environment variable storage
  - **Property 30: Sensitive field environment variable storage**
  - **Validates: Requirements 16.2, 16.3**

- [ ]* 15.2 Write property test for sensitive field runtime resolution
  - **Property 31: Sensitive field runtime resolution**
  - **Validates: Requirements 16.4, 16.5**

- [ ]* 15.3 Write property test for sensitive field redaction
  - **Property 32: Sensitive field redaction**
  - **Validates: Requirements 16.6, 16.7, 16.8**

- [ ]* 15.4 Write property test for sensitive field deferred resolution
  - **Property 33: Sensitive field deferred resolution**
  - **Validates: Requirements 16.9**

- [ ] 16. Checkpoint: Deferred operations and secrets
  - **Deliverables**: Deferred operations registry with rollback, secrets management with environment variable references
  - **Verification**: Run integration test that registers deferred operations, completes workflow, verifies execution order; test rollback on failure; test sensitive fields are stored as env var references and resolved at runtime
  - **Test Script**: `tests/checkpoints/test_checkpoint_5_operations_secrets.py`
  - Ensure all tests pass, ask the user if questions arise

- [ ] 17. Implement adapter integration layer
  - Create `AdapterQuestionTranslator` class
  - Implement `translate_input_prompt()` method for InputPrompt → QuestionNode conversion
  - Implement type mapping between InputPrompt and workflow DSL types
  - Create `AdapterWorkflowGenerator` class
  - Implement `generate_workflow_from_adapters()` method
  - Integrate with existing AdapterRegistry from zerotouch-engine
  - Implement PlatformContext construction from session answers
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.7, 9.11_

- [ ]* 17.1 Write property test for InputPrompt to question translation
  - **Property 21: InputPrompt to question translation**
  - **Validates: Requirements 9.11**

- [ ]* 17.2 Write property test for adapter loading and context construction
  - **Property 17: Adapter loading and context construction**
  - **Validates: Requirements 9.2, 9.3, 9.4**

- [ ] 18. Implement cross-adapter dependencies
  - Implement answer merging across multiple adapters in PlatformContext
  - Add cross-adapter answer accessibility
  - Implement adapter failure state preservation
  - _Requirements: 9.5, 9.6, 9.8_

- [ ]* 18.1 Write property test for cross-adapter answer accessibility
  - **Property 18: Cross-adapter answer accessibility**
  - **Validates: Requirements 9.5, 9.6**

- [ ]* 18.2 Write property test for adapter failure state preservation
  - **Property 19: Adapter failure state preservation**
  - **Validates: Requirements 9.8**

- [ ] 19. Implement dynamic choice resolution
  - Create `DynamicChoiceResolver` class
  - Implement `resolve_choices()` method calling adapter's `get_dynamic_choices()`
  - Integrate dynamic choice resolution into question presentation
  - Add caching for dynamic choices to avoid redundant API calls
  - _Requirements: 9.9_

- [ ]* 19.1 Write property test for dynamic choice resolution
  - **Property 20: Dynamic choice resolution**
  - **Validates: Requirements 9.9**

- [ ] 20. Implement adapter read-only restrictions
  - Add validation to ensure adapters only perform read operations during traversal
  - Implement adapter operation type checking (validation vs mutation)
  - Defer state-mutating operations to deferred operations registry
  - _Requirements: 9.10_

- [ ] 21. Checkpoint: Adapter integration
  - **Deliverables**: Complete adapter integration layer, dynamic workflow generation from adapters, cross-adapter dependencies, dynamic choice resolution
  - **Verification**: Run integration test that loads Hetzner and Cilium adapters, generates workflow from their InputPrompts, answers questions, constructs PlatformContext with merged answers, verifies cross-adapter answer access, tests dynamic choices
  - **Test Script**: `tests/checkpoints/test_checkpoint_6_adapter_integration.py`
  - Ensure all tests pass, ask the user if questions arise

- [ ] 22. Implement MCP JSON-RPC protocol layer
  - Create JSON-RPC message parser and validator
  - Implement stdio transport for local CLI communication
  - Implement HTTP transport for network communication
  - Add JSON-RPC error response formatting
  - Implement request routing to workflow engine methods
  - _Requirements: 6.1, 6.2, 6.3, 6.5_

- [ ]* 22.1 Write property test for JSON-RPC parsing
  - **Property 10: JSON-RPC parsing correctness**
  - **Validates: Requirements 6.2, 6.3, 6.5**

- [ ] 23. Implement MCP Server with stateless architecture
  - Create `MCPServer` class with stateless request handling
  - Implement `start_workflow` endpoint
  - Implement `submit_answer` endpoint
  - Implement `restore_session` endpoint
  - Implement `restart_workflow` endpoint
  - Implement `MCPServerObserver` for JSON-RPC notifications
  - Add state blob encoding/decoding (base64)
  - _Requirements: 6.6, 6.7, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 10.1, 10.2, 10.3_

- [ ]* 23.1 Write property test for session ID uniqueness
  - **Property 11: Session ID uniqueness**
  - **Validates: Requirements 7.1, 10.3**

- [ ]* 23.2 Write property test for workflow start response completeness
  - **Property 12: Workflow start response completeness**
  - **Validates: Requirements 7.2**

- [ ]* 23.3 Write property test for workflow restart initialization
  - **Property 14: Workflow restart initialization**
  - **Validates: Requirements 7.7, 10.1, 10.2, 10.3**

- [ ] 24. Implement transport security strategies
  - Add `TransportSecurityMode` enum (Development, Production)
  - Implement development mode with localhost-only HTTP
  - Implement production mode with mandatory TLS
  - Add TLS certificate verification for production mode
  - Implement connection rejection for non-TLS in production
  - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

- [ ]* 24.1 Write property test for production mode TLS enforcement
  - **Property 34: Production mode TLS enforcement**
  - **Validates: Requirements 17.3**

- [ ] 25. Checkpoint: MCP protocol and server
  - **Deliverables**: Complete MCP server with JSON-RPC endpoints, stdio and HTTP transports, stateless architecture, transport security modes
  - **Verification**: Run integration test that starts MCP server, connects via stdio, starts workflow, submits answers, restores session, restarts workflow; verify all JSON-RPC responses are valid, state blobs work correctly, server remains stateless
  - **Test Script**: `tests/checkpoints/test_checkpoint_7_mcp_server.py`
  - Ensure all tests pass, ask the user if questions arise

- [ ] 26. Implement CLI client with FilesystemStore
  - Create CLI client using Click framework
  - Implement `ztc workflow start` command
  - Implement `ztc workflow answer` command
  - Implement `ztc workflow restore` command
  - Implement `ztc workflow restart` command
  - Integrate FilesystemStore for `.ztc/session.json` persistence
  - Add JSON-RPC client for MCP server communication
  - Implement event notification display
  - _Requirements: 2.2, 2.4, 6.1, 6.2, 6.3, 6.7, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

- [ ] 27. Implement error handling and formatting
  - Implement validation error responses with field context
  - Implement workflow DSL error responses with line numbers
  - Implement session error responses with version mismatch details
  - Implement adapter error responses with cause information
  - Implement secret resolution error responses
  - Implement transport error responses (JSON-RPC standard codes)
  - Add sensitive information redaction in error messages
  - _Requirements: 7.5, 11.4, 12.7_

- [ ] 28. Checkpoint: CLI client and error handling
  - **Deliverables**: Complete CLI client with all workflow commands, FilesystemStore integration, comprehensive error handling
  - **Verification**: Run end-to-end integration test using CLI commands: start workflow, answer questions with valid/invalid inputs, verify error messages, save session, restore session, restart workflow; verify filesystem persistence works correctly
  - **Test Script**: `tests/checkpoints/test_checkpoint_8_cli_end_to_end.py`
  - Ensure all tests pass, ask the user if questions arise

- [ ] 29. Create Hypothesis custom strategies
  - Implement `workflows()` strategy for generating random valid workflows
  - Implement `question_nodes()` strategy for generating random questions
  - Implement `validation_rules()` strategy for generating random validation rules
  - Implement `answer_data()` strategy for generating random answers
  - Implement `transitions()` strategy for generating random state transitions
  - Add edge case handling in generators (empty workflows, single questions, deeply nested)
  - _Testing infrastructure for all property tests_

- [ ] 30. Write comprehensive property test suite
  - Implement all 34 property tests from design document
  - Configure each test to run minimum 100 iterations
  - Add property tags referencing design document
  - Verify all properties pass with generated test data
  - _Validates all requirements through property-based testing_

- [ ] 31. Final checkpoint: Complete system validation
  - **Deliverables**: Complete MCP Workflow Engine with all features, comprehensive property test suite, CLI client, adapter integration
  - **Verification**: Run full integration test suite covering all user journeys: simple workflows, nested workflows, adapter-generated workflows, session persistence, secrets management, error handling; verify all 34 properties pass with 100+ iterations
  - **Test Script**: `tests/checkpoints/test_checkpoint_9_full_system.py`
  - Ensure all tests pass, ask the user if questions arise

## Notes

- Tasks marked with `*` are optional property-based tests that can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation with concrete test scripts
- Property tests use Hypothesis with minimum 100 iterations
- Follow user journey order: core traversal → persistence → events → DSL → validation → advanced features → adapters → MCP protocol → CLI
- Checkpoints block next phase until validation passes
- All checkpoint test scripts must validate real behavior using actual workflow engine components

## Testing Guidelines (Critical)

**Integration Tests Only:**
- DO NOT write unit tests - all tests must be integration tests
- Tests must validate real end-to-end behavior, not isolated functions

**Production Code Usage:**
- Tests MUST use the exact same service classes, dependency injection, and business logic as production
- This ensures maximum code coverage and validates actual production behavior
- Import and instantiate real classes (QuestionPathTraverser, WorkflowDSLParser, MCPServer, etc.)

**No Mocks or Fakes:**
- DO NOT use mocks, stubs, or fake implementations
- Tests must exercise actual production code paths
- Use real FilesystemStore, real adapters, real JSON-RPC communication

**Validation Focus:**
- Validate artifacts produced by the system (serialized state, workflow responses, file contents)
- Verify observable behavior (questions presented, answers accepted, state transitions)
- Check integration points (adapter loading, MCP protocol compliance, session restoration)
