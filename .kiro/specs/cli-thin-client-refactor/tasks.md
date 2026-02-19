# Implementation Plan: CLI Thin Client Refactor

## Overview

This plan refactors the CLI from thick client to thin presentation layer by moving business logic into workflow_engine. Tasks are ordered to maintain working code at each step, with incremental migration from MCP-based to direct import architecture.

## Tasks

- [x] 1. Create engine service layer structure
  - Create workflow_engine/services/ directory
  - Create workflow_engine/orchestration/ directory
  - Create workflow_engine/parsers/ directory
  - Update workflow_engine/__init__.py to export new modules
  - _Requirements: 8.1, 8.2, 8.3, 8.5_

- [ ] 2. Implement parser layer
  - [x] 2.1 Create EnvFileParser
    - Implement parse() method for .env files
    - Handle comments, empty lines, quoted values
    - _Requirements: 4.1, 4.2, 4.3_
  
  - [ ]* 2.2 Write property test for env file parsing
    - **Property 4: Env File Parsing Consistency**
    - **Validates: Requirements 4.1, 4.2, 4.3**
  
  - [x] 2.3 Add env var validation to EnvFileParser
    - Implement validate() method
    - Check key format (uppercase, underscores)
    - Check non-empty values
    - _Requirements: 4.4_
  
  - [ ]* 2.4 Write property test for env var validation
    - **Property 5: Invalid Env Vars Rejected**
    - **Validates: Requirements 4.4**
  
  - [x] 2.5 Create YAMLParser
    - Implement load() and save() methods
    - Use PyYAML with safe_load
    - _Requirements: 2.1, 2.2_

- [ ] 3. Implement PlatformConfigService
  - [x] 3.1 Create PlatformConfig and PlatformInfo models
    - Define Pydantic models for platform.yaml structure
    - _Requirements: 2.1, 2.2_
  
  - [x] 3.2 Implement PlatformConfigService
    - Implement exists(), load(), save() methods
    - Implement save_adapter() for incremental updates
    - Implement load_adapters() for cross-adapter access
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  
  - [ ]* 3.3 Write property test for platform config round trip
    - **Property 1: Platform Config Round Trip**
    - **Validates: Requirements 2.5**
  
  - [ ]* 3.4 Write property test for adapter incremental save
    - **Property 3: Adapter Config Incremental Save**
    - **Validates: Requirements 2.3, 2.4**

- [ ] 4. Implement SessionStateService
  - [x] 4.1 Move FilesystemStore to workflow_engine
    - Move from ztp_cli/storage.py to workflow_engine/storage/session_store.py
    - Keep existing SessionStore interface
    - _Requirements: 3.1, 3.2, 3.3_
  
  - [x] 4.2 Create SessionStateService
    - Implement save(), load(), delete(), exists() methods
    - Wrap SessionStore with service interface
    - _Requirements: 3.1, 3.2, 3.3_
  
  - [ ]* 4.3 Write property test for session state round trip
    - **Property 2: Session State Round Trip**
    - **Validates: Requirements 3.5**

- [ ] 5. Implement ValidationOrchestrator
  - [x] 5.1 Create ValidationResult and ScriptResult models
    - Define dataclasses for validation results
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  
  - [x] 5.2 Implement ValidationOrchestrator
    - Implement validate_adapter() method
    - Execute all init scripts for adapter
    - Return structured results with stdout/stderr
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [ ]* 5.3 Write property test for validation script execution
    - **Property 6: Validation Script Execution**
    - **Validates: Requirements 5.2**
  
  - [ ]* 5.4 Write property test for validation failure errors
    - **Property 7: Validation Failure Returns Errors**
    - **Validates: Requirements 5.3**
  
  - [ ]* 5.5 Write property test for validation success
    - **Property 8: Validation Success Marks Validated**
    - **Validates: Requirements 5.4**

- [ ] 6. Implement PrerequisiteChecker
  - [x] 6.1 Create PrerequisiteResult model
    - Define dataclass for prerequisite check results
    - _Requirements: 6.1_
  
  - [x] 6.2 Implement PrerequisiteChecker
    - Implement check() method
    - Check platform.yaml existence
    - Validate required directories
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  
  - [ ]* 6.3 Write property test for existing config detection
    - **Property 9: Prerequisite Check Detects Existing Config**
    - **Validates: Requirements 6.2, 6.3**
  
  - [ ]* 6.4 Write property test for directory validation
    - **Property 10: Prerequisite Check Validates Directories**
    - **Validates: Requirements 6.4**

- [x] 7. Checkpoint - Ensure all service tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement InitWorkflowOrchestrator
  - [x] 8.1 Create WorkflowResult model
    - Define dataclass for workflow operation results
    - _Requirements: 1.1, 1.2_
  
  - [x] 8.2 Implement InitWorkflowOrchestrator
    - Implement check_prerequisites() method
    - Implement start() method
    - Implement answer() method
    - Integrate PlatformConfigService for incremental saves
    - Integrate SessionStateService for crash recovery
    - Integrate ValidationOrchestrator for validation
    - _Requirements: 1.1, 1.2, 2.4, 3.4, 5.1_
  
  - [ ]* 8.3 Write property test for engine returns native objects
    - **Property 12: Engine Returns Native Python Objects**
    - **Validates: Requirements 1.4**
  
  - [ ]* 8.4 Write property test for structured errors
    - **Property 11: Engine Returns Structured Errors**
    - **Validates: Requirements 11.1, 11.5**

- [x] 9. Create ValidationService wrapper
  - [x] 9.1 Implement ValidationService
    - Wrap ValidationOrchestrator with service interface
    - _Requirements: 5.1_

- [x] 10. Update InitWorkflow to use services
  - [x] 10.1 Modify InitWorkflow._validate_and_continue
    - Remove direct ScriptExecutor usage
    - Use ValidationOrchestrator instead
    - _Requirements: 5.1, 5.2_
  
  - [x] 10.2 Modify InitWorkflow._build_cross_adapter_config
    - Use PlatformConfigService.load_adapters() instead of state
    - _Requirements: 2.1_

- [x] 11. Refactor CLI to use orchestrator directly
  - [x] 11.1 Create engine_bridge.py module
    - Centralize all workflow_engine imports
    - Re-export orchestrators, services, models, storage, parsers
    - Provide single point of access for CLI
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [x] 11.2 Create new InitCommand class
    - Implement run() method with UI logic only
    - Import from engine_bridge only
    - Use InitWorkflowOrchestrator directly (no MCP)
    - Display questions with Rich console
    - Collect input with prompts
    - Display validation results with colors
    - _Requirements: 1.1, 1.2, 1.3, 7.1, 7.2, 7.3, 7.4, 13.3_
  
  - [x] 11.3 Update init.py to use InitCommand
    - Replace InitOrchestrator with InitCommand
    - Remove MCP client instantiation
    - _Requirements: 1.1, 1.2, 1.3_
  
  - [x] 11.4 Remove MCP-related code from CLI
    - Delete mcp_client.py
    - Delete storage.py (moved to engine)
    - Remove MCP dependencies from CLI
    - _Requirements: 1.3_

- [x] 12. Checkpoint - Test init command end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Export public engine APIs
  - [x] 13.1 Update workflow_engine/__init__.py
    - Export InitWorkflowOrchestrator
    - Export PlatformConfigService
    - Export SessionStateService
    - Export ValidationService
    - Export all result models
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  
  - [ ]* 13.2 Write property test for programmatic API
    - **Property 13: Programmatic API Returns Unformatted Data**
    - **Validates: Requirements 9.5**

- [x] 14. Update render command to use engine directly
  - [x] 14.1 Refactor RenderCommand
    - Remove MCP client usage
    - Import from engine_bridge only
    - Use PlatformConfigService to load config
    - _Requirements: 1.1, 1.2, 10.2, 13.3_

- [x] 15. Update bootstrap command to use engine directly
  - [x] 15.1 Refactor BootstrapCommand
    - Remove MCP client usage
    - Import from engine_bridge only
    - _Requirements: 1.1, 1.2, 10.3, 13.3_

- [x] 16. Update validate command to use engine directly
  - [x] 16.1 Refactor ValidateCommand
    - Remove MCP client usage
    - Import from engine_bridge only
    - _Requirements: 1.1, 1.2, 10.4, 13.3_

- [x] 17. Final integration testing
  - [ ]* 17.1 Test backward compatibility for all commands
    - Verify ztc init produces same output
    - Verify ztc render produces same output
    - Verify ztc bootstrap executes same pipeline
    - Verify ztc validate performs same checks
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 18. Final checkpoint - All tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Integration tests verify backward compatibility
