# Requirements Document: CLI Thin Client Refactor

## Introduction

This specification defines the requirements for refactoring the ZeroTouch CLI from a thick client with embedded business logic to a thin presentation layer that directly imports and uses the workflow_engine. The refactoring eliminates the MCP protocol overhead for local CLI usage while moving all business logic into the reusable workflow_engine core.

## Glossary

- **CLI**: Command-Line Interface - the user-facing terminal application (ztp_cli)
- **Workflow_Engine**: Core business logic library containing orchestration, services, and domain logic
- **MCP**: Model Context Protocol - currently used for CLI-to-engine communication (to be removed)
- **Platform_Config**: The platform.yaml file containing adapter configurations
- **Session_State**: Workflow execution state including answers and current position
- **Init_Orchestrator**: CLI component coordinating the init workflow
- **Adapter**: Pluggable component for platform services (cloud, git, secrets, etc.)
- **Validation_Script**: Executable script that validates adapter configuration
- **Business_Logic**: Domain logic including validation, orchestration, and state management

## Requirements

### Requirement 1: Engine Direct Import

**User Story:** As a developer, I want the CLI to import workflow_engine modules directly, so that there is no MCP protocol overhead for local usage.

#### Acceptance Criteria

1. WHEN the CLI executes any command, THE CLI SHALL import workflow_engine modules using Python import statements
2. WHEN the CLI needs engine functionality, THE CLI SHALL call engine functions directly without network serialization
3. THE CLI SHALL NOT use MCP client classes for local workflow execution
4. THE CLI SHALL NOT serialize/deserialize data for engine communication

### Requirement 2: Platform Config Management in Engine

**User Story:** As a developer, I want platform.yaml management logic in the engine, so that config persistence is reusable across interfaces.

#### Acceptance Criteria

1. THE Workflow_Engine SHALL provide a PlatformConfigService for reading platform.yaml
2. THE Workflow_Engine SHALL provide a PlatformConfigService for writing platform.yaml
3. THE Workflow_Engine SHALL provide a PlatformConfigService for incremental adapter config updates
4. WHEN an adapter completes validation, THE Workflow_Engine SHALL persist the adapter config to platform.yaml
5. WHEN loading platform config, THE Workflow_Engine SHALL parse YAML and return structured data
6. THE CLI SHALL NOT contain platform.yaml file I/O logic

### Requirement 3: Session State Management in Engine

**User Story:** As a developer, I want session state persistence in the engine, so that workflow resumption works consistently.

#### Acceptance Criteria

1. THE Workflow_Engine SHALL provide a SessionStateService for saving workflow state
2. THE Workflow_Engine SHALL provide a SessionStateService for loading workflow state
3. THE Workflow_Engine SHALL provide a SessionStateService for deleting workflow state
4. WHEN a workflow is interrupted, THE Workflow_Engine SHALL persist the current state to .zerotouch-cache/init-state.json
5. WHEN resuming a workflow, THE Workflow_Engine SHALL restore state from .zerotouch-cache/init-state.json
6. THE CLI SHALL NOT contain session state file I/O logic

### Requirement 4: Environment File Parsing in Engine

**User Story:** As a developer, I want .env file parsing in the engine, so that environment-specific defaults are handled consistently.

#### Acceptance Criteria

1. THE Workflow_Engine SHALL provide an EnvFileParser for parsing .env files
2. WHEN loading environment defaults, THE Workflow_Engine SHALL read .env.<environment> files
3. WHEN loading global secrets, THE Workflow_Engine SHALL read .env.global files
4. THE Workflow_Engine SHALL validate environment variable formats
5. THE CLI SHALL NOT contain .env file parsing logic

### Requirement 5: Validation Orchestration in Engine

**User Story:** As a developer, I want validation workflow orchestration in the engine, so that validation logic is reusable.

#### Acceptance Criteria

1. THE Workflow_Engine SHALL provide a ValidationOrchestrator for executing validation scripts
2. WHEN an adapter config is complete, THE Workflow_Engine SHALL execute all validation scripts for that adapter
3. WHEN a validation script fails, THE Workflow_Engine SHALL return error details including stdout and stderr
4. WHEN all validation scripts pass, THE Workflow_Engine SHALL mark the adapter as validated
5. THE Workflow_Engine SHALL log validation results to .zerotouch-cache/init-logs/
6. THE CLI SHALL NOT contain validation execution logic

### Requirement 6: Prerequisite Checks in Engine

**User Story:** As a developer, I want prerequisite checks in the engine, so that pre-flight validation is consistent.

#### Acceptance Criteria

1. THE Workflow_Engine SHALL provide a PrerequisiteChecker for validating init preconditions
2. WHEN init starts, THE Workflow_Engine SHALL check if platform.yaml already exists
3. WHEN platform.yaml exists, THE Workflow_Engine SHALL return an error preventing init execution
4. THE Workflow_Engine SHALL validate required directories exist or can be created
5. THE CLI SHALL NOT contain prerequisite checking logic

### Requirement 7: CLI as Presentation Layer

**User Story:** As a user, I want the CLI to handle only UI concerns, so that the interface is clean and focused.

#### Acceptance Criteria

1. THE CLI SHALL display questions to users using Rich console formatting
2. THE CLI SHALL collect user input through interactive prompts
3. THE CLI SHALL display validation results with colored output
4. THE CLI SHALL display progress spinners during engine operations
5. THE CLI SHALL NOT contain business logic or domain rules
6. THE CLI SHALL NOT perform file I/O except for displaying file paths

### Requirement 8: Engine Module Structure

**User Story:** As a developer, I want a clear engine module structure, so that the codebase is maintainable.

#### Acceptance Criteria

1. THE Workflow_Engine SHALL organize code into orchestration/, services/, storage/, parsers/, adapters/, engine/, and models/ directories
2. THE Workflow_Engine SHALL place InitWorkflowOrchestrator in orchestration/ directory
3. THE Workflow_Engine SHALL place PlatformConfigService, SessionStateService, and ValidationService in services/ directory
4. THE Workflow_Engine SHALL place FilesystemStore in storage/ directory
5. THE Workflow_Engine SHALL place EnvFileParser in parsers/ directory
6. THE Workflow_Engine SHALL maintain existing adapters/ and engine/ directories

### Requirement 9: Programmatic Engine Usage

**User Story:** As a developer, I want to use the engine programmatically, so that I can build APIs or other interfaces.

#### Acceptance Criteria

1. THE Workflow_Engine SHALL expose a public API for starting init workflows
2. THE Workflow_Engine SHALL expose a public API for submitting answers to workflows
3. THE Workflow_Engine SHALL expose a public API for loading platform configurations
4. THE Workflow_Engine SHALL expose a public API for validating adapter configs
5. WHEN called programmatically, THE Workflow_Engine SHALL return structured data without CLI formatting
6. THE Workflow_Engine SHALL NOT depend on CLI libraries or terminal output

### Requirement 10: Backward Compatibility

**User Story:** As a user, I want existing CLI commands to work unchanged, so that my workflows are not disrupted.

#### Acceptance Criteria

1. WHEN running `ztc init`, THE CLI SHALL execute the same workflow as before refactoring
2. WHEN running `ztc render`, THE CLI SHALL produce identical output as before refactoring
3. WHEN running `ztc bootstrap`, THE CLI SHALL execute the same pipeline as before refactoring
4. WHEN running `ztc validate`, THE CLI SHALL perform the same checks as before refactoring
5. THE CLI SHALL maintain all existing command-line arguments and options

### Requirement 11: Error Handling Consistency

**User Story:** As a user, I want consistent error messages, so that I can troubleshoot issues effectively.

#### Acceptance Criteria

1. WHEN the engine encounters an error, THE Workflow_Engine SHALL return structured error objects
2. WHEN displaying errors, THE CLI SHALL format engine errors with Rich console styling
3. WHEN validation fails, THE CLI SHALL display script names, error messages, and log file locations
4. WHEN prerequisites fail, THE CLI SHALL display clear instructions for resolution
5. THE Workflow_Engine SHALL NOT format errors for terminal display

### Requirement 12: Testing Separation

**User Story:** As a developer, I want to test engine logic independently, so that tests are fast and focused.

#### Acceptance Criteria

1. THE Workflow_Engine SHALL be testable without CLI dependencies
2. THE Workflow_Engine SHALL be testable without terminal I/O
3. WHEN testing engine services, tests SHALL use in-memory storage or mocks
4. WHEN testing CLI presentation, tests SHALL mock engine calls
5. THE Workflow_Engine SHALL NOT require Rich console or Typer for testing

### Requirement 13: CLI Engine Bridge

**User Story:** As a developer, I want a single bridge module for engine imports, so that CLI-to-engine coupling is centralized and maintainable.

#### Acceptance Criteria

1. THE CLI SHALL provide an engine_bridge.py module that centralizes all workflow_engine imports
2. THE engine_bridge SHALL re-export all public workflow_engine APIs (orchestrators, services, models)
3. WHEN CLI commands need engine functionality, THEY SHALL import from engine_bridge only
4. THE CLI SHALL NOT import directly from workflow_engine modules except via engine_bridge
5. THE engine_bridge SHALL serve as the single point of coupling between CLI and engine
