# Task List: ZTC Phase 1 - Multi-Adapter Foundation

## Phase 1: Project Setup & Core Infrastructure

- [ ] 1. Initialize ZTC project structure with Poetry
- [ ] 2. Set up Python package structure (ztc/ directory)
- [ ] 3. Configure pyproject.toml with dependencies (Typer, Rich, Pydantic, Jinja2, PyYAML)
- [ ] 4. Create base directory structure for adapters, templates, and scripts
- [ ] 5. Set up pytest configuration and test directory structure
- [ ] 6. **CHECKPOINT 1: Project Foundation Ready**
  - **Deliverable**: ZTC project initialized with Poetry, all dependencies installed, directory structure created
  - **Verification Criteria**:
    - `poetry install` completes successfully
    - `poetry run python -c "import typer, rich, pydantic, jinja2, yaml"` succeeds
    - Directory structure matches design spec (ztc/adapters/, ztc/cli.py, tests/)
  - **Test Script**: Run `poetry run pytest tests/test_project_setup.py` to validate package imports and directory structure
  - **Success Criteria**: All dependencies importable, project structure validated, pytest runs successfully

## Phase 2: Capability Interface & Base Adapter Contract

- [ ] 7. Implement Capability enum and Pydantic models (ztc/interfaces/capabilities.py)
- [ ] 8. Create CAPABILITY_CONTRACTS registry binding enums to models
- [ ] 9. Implement PlatformAdapter abstract base class (ztc/adapters/base.py)
- [ ] 10. Add InputPrompt, ScriptReference, PipelineStage, AdapterOutput dataclasses
- [ ] 11. Implement ScriptReference.__post_init__ with static validation
- [ ] 12. Create AdapterRegistry class for adapter discovery and loading
- [ ] 13. Write unit tests for capability contracts and base adapter interface
- [ ] 14. **CHECKPOINT 2: Adapter Contract Established**
  - **Deliverable**: Type-safe capability system and adapter base class with validation
  - **Verification Criteria**:
    - All Capability enums map to Pydantic models in CAPABILITY_CONTRACTS
    - PlatformAdapter abstract methods defined (get_required_inputs, pre_work_scripts, post_work_scripts, validation_scripts, render)
    - ScriptReference validates script existence at instantiation
  - **Test Script**: Run `poetry run pytest tests/unit/test_adapter_contract.py` to validate capability contracts, adapter interface, and script validation
  - **Success Criteria**: All capability models validate correctly, adapter interface enforces contracts, script validation catches missing resources

## Phase 3: Hetzner Adapter Implementation

- [ ] 15. Create Hetzner adapter directory structure (ztc/adapters/hetzner/)
- [ ] 16. Implement HetznerConfig Pydantic model with validation
- [ ] 17. Create adapter.yaml metadata file for Hetzner
- [ ] 18. Implement HetznerAdapter class with get_required_inputs()
- [ ] 19. Create embedded scripts (enable-rescue-mode.sh, validate-server-ids.sh)
- [ ] 20. Implement HetznerAdapter.render() with async API calls
- [ ] 21. Add CloudInfrastructureCapability output to render()
- [ ] 22. Write unit tests for Hetzner adapter configuration and rendering
- [ ] 23. **CHECKPOINT 3: Hetzner Adapter Functional**
  - **Deliverable**: Hetzner adapter with API integration and capability output
  - **Verification Criteria**:
    - HetznerAdapter validates config via Pydantic model
    - render() method queries Hetzner API and returns server IDs
    - CloudInfrastructureCapability output includes provider, server_ids, rescue_mode_enabled
    - Scripts embedded and accessible via get_embedded_script()
  - **Test Script**: Run `poetry run pytest tests/integration/test_hetzner_adapter.py` to validate Hetzner API integration (mocked), config validation, and capability output
  - **Success Criteria**: Adapter renders successfully with mocked API, capability data validates against contract, scripts extractable

## Phase 4: Cilium Adapter Implementation

- [ ] 24. Create Cilium adapter directory structure (ztc/adapters/cilium/)
- [ ] 25. Implement CiliumConfig Pydantic model
- [ ] 26. Create adapter.yaml metadata with capability requirements (kubernetes-api)
- [ ] 27. Implement CiliumAdapter class with BGP configuration support
- [ ] 28. Create Jinja2 templates (manifests.yaml.j2)
- [ ] 29. Create embedded scripts (wait-cilium.sh, wait-gateway-api.sh, validate-cni.sh)
- [ ] 30. Implement CiliumAdapter.render() with template rendering
- [ ] 31. Add CNIArtifacts and GatewayAPICapability outputs
- [ ] 32. Implement get_invalid_fields() for differential validation
- [ ] 33. Write unit tests for Cilium adapter and template rendering
- [ ] 34. **CHECKPOINT 4: Cilium Adapter Functional**
  - **Deliverable**: Cilium adapter with template rendering and capability outputs
  - **Verification Criteria**:
    - CiliumAdapter renders manifests via Jinja2 templates
    - CNIArtifacts capability includes manifests content
    - GatewayAPICapability indicates CRDs embedded
    - Differential validation detects OS changes
  - **Test Script**: Run `poetry run pytest tests/integration/test_cilium_adapter.py` to validate template rendering, capability outputs, and validation logic
  - **Success Criteria**: Templates render correctly, capability data validates, differential validation works

## Phase 5: Talos Adapter Implementation

- [ ] 35. Create Talos adapter directory structure (ztc/adapters/talos/)
- [ ] 36. Implement TalosConfig and NodeConfig Pydantic models
- [ ] 37. Create TalosScripts enum for static validation
- [ ] 38. Create adapter.yaml metadata with capability provides/requires
- [ ] 39. Implement TalosAdapter class with node configuration
- [ ] 40. Create Jinja2 templates (controlplane.yaml.j2, worker.yaml.j2, talosconfig.j2)
- [ ] 41. Create embedded scripts with context_data (02-embed-network-manifests.sh, 03-install-talos.sh, 04-bootstrap-talos.sh, 05-add-worker-nodes.sh, validate-cluster.sh)
- [ ] 42. Implement TalosAdapter.render() with per-node config generation
- [ ] 43. Add KubernetesAPICapability output
- [ ] 44. Write unit tests for Talos adapter and multi-node rendering
- [ ] 45. **CHECKPOINT 5: Talos Adapter Functional**
  - **Deliverable**: Talos adapter with multi-node config generation and capability output
  - **Verification Criteria**:
    - TalosAdapter renders separate configs for controlplane and worker nodes
    - KubernetesAPICapability includes cluster_endpoint and kubeconfig_path
    - Scripts use context_data instead of args
    - Templates embed CNI manifests from upstream capability
  - **Test Script**: Run `poetry run pytest tests/integration/test_talos_adapter.py` to validate multi-node rendering, capability integration, and context file generation
  - **Success Criteria**: Node configs render correctly, capability data validates, context files generated for scripts

## Phase 6: CLI Framework & Init Workflow

- [ ] 46. Implement CLI app structure with Typer (ztc/cli.py)
- [ ] 47. Create SelectionGroup dataclass for dynamic UI grouping
- [ ] 48. Implement build_selection_groups() for registry-driven UI
- [ ] 49. Create InitWorkflow class with progressive input collection
- [ ] 50. Implement handle_group_selection() with conflict cleanup
- [ ] 51. Implement collect_adapter_inputs() with Pydantic validation
- [ ] 52. Implement validate_downstream_adapters() with differential validation
- [ ] 53. Add display_summary() with Rich table output
- [ ] 54. Implement platform.yaml generation and writing
- [ ] 55. Add --resume flag support for resuming configuration
- [ ] 56. Write integration tests for init workflow with mocked prompts
- [ ] 57. **CHECKPOINT 6: Init Command Functional**
  - **Deliverable**: Interactive CLI wizard generating platform.yaml
  - **Verification Criteria**:
    - `ztc init` prompts for cloud provider, network, OS selections
    - Adapter-specific inputs collected with validation
    - platform.yaml generated with correct structure
    - --resume flag loads existing config and skips completed sections
  - **Test Script**: Run `poetry run pytest tests/integration/test_init_workflow.py` with mocked prompts to validate full init flow and platform.yaml generation
  - **Success Criteria**: Init workflow completes, platform.yaml validates against schema, resume functionality works

## Phase 7: Version Registry & Remote Fetch

- [ ] 58. Create embedded versions.yaml with component versions
- [ ] 59. Implement VersionRegistry class with embedded version loading
- [ ] 60. Add start_background_fetch() for async remote version fetch
- [ ] 61. Implement get_versions_async() with explicit await and timeout
- [ ] 62. Add version source tracking (_version_source field)
- [ ] 63. Implement _fetch_remote_async() with signature verification
- [ ] 64. Add get_version_source() for user transparency
- [ ] 65. Integrate version registry into init workflow with user notification
- [ ] 66. Write unit tests for version fetching and fallback behavior
- [ ] 67. **CHECKPOINT 7: Version Management Functional**
  - **Deliverable**: Version registry with remote fetch and explicit user notification
  - **Verification Criteria**:
    - Embedded versions.yaml loads successfully
    - Remote fetch attempts with timeout (2s default)
    - User notified of version source (remote vs embedded)
    - Fallback to embedded versions on timeout/error
  - **Test Script**: Run `poetry run pytest tests/unit/test_version_registry.py` to validate version loading, remote fetch with mocked network, and fallback behavior
  - **Success Criteria**: Version registry loads embedded versions, remote fetch works with mocks, user notification displays correct source

## Phase 8: Engine & Dependency Resolution

- [ ] 68. Implement PlatformEngine class (ztc/engine.py)
- [ ] 69. Create shared Jinja2 environment with PrefixLoader
- [ ] 70. Implement _create_shared_jinja_env() with adapter namespacing
- [ ] 71. Create ContextSnapshot class for immutable context
- [ ] 72. Implement PlatformContext class for mutable engine state
- [ ] 73. Add get_capability_data() with enum-based type-safe access
- [ ] 74. Implement DependencyResolver with topological sort
- [ ] 75. Add capability registry building and validation
- [ ] 76. Implement resolve_adapters() with phase grouping
- [ ] 77. Write unit tests for dependency resolution and capability validation
- [ ] 78. **CHECKPOINT 8: Engine Core Functional**
  - **Deliverable**: Engine with dependency resolution and capability management
  - **Verification Criteria**:
    - Shared Jinja environment created with adapter prefixes
    - Dependency resolver orders adapters correctly (Hetzner → Talos → Cilium)
    - Capability registry validates requirements against providers
    - ContextSnapshot provides immutable read-only access
  - **Test Script**: Run `poetry run pytest tests/unit/test_engine_core.py` to validate dependency resolution, capability validation, and context management
  - **Success Criteria**: Adapters resolve in correct order, capability contracts enforced, context immutability maintained

## Phase 9: Render Pipeline Implementation

- [ ] 79. Implement Engine.render() async method
- [ ] 80. Add workspace creation and cleanup logic
- [ ] 81. Implement adapter rendering loop with context snapshots
- [ ] 82. Add write_adapter_output() for manifest writing
- [ ] 83. Implement generate_pipeline_yaml() from adapter stages
- [ ] 84. Add write_debug_scripts() for observability
- [ ] 85. Implement validate_artifacts() against output schemas
- [ ] 86. Add atomic_swap_generated() for atomic directory replacement
- [ ] 87. Implement lock file generation with artifact hashing
- [ ] 88. Add streaming file hashing (hash_file with chunks)
- [ ] 89. Create render CLI command with --debug and --partial flags
- [ ] 90. Write integration tests for full render pipeline
- [ ] 91. **CHECKPOINT 9: Render Pipeline Functional**
  - **Deliverable**: Render command generating artifacts and pipeline YAML
  - **Verification Criteria**:
    - `ztc render` reads platform.yaml and executes adapters
    - Manifests written to platform/generated/ directory
    - pipeline.yaml generated with all stages
    - lock.json created with artifact hashes
    - Debug scripts written to platform/generated/debug/
  - **Test Script**: Run `poetry run pytest tests/integration/test_render_pipeline.py` to validate full render flow with all 3 adapters
  - **Success Criteria**: Render completes successfully, all artifacts generated, lock file validates, debug scripts extractable

## Phase 10: Bootstrap Command & Runtime Dependencies

- [ ] 92. Implement SecureTempDir context manager with signal handling
- [ ] 93. Add _signal_handler() for SIGINT/SIGTERM cleanup
- [ ] 94. Create VacuumCommand for stale temp directory cleanup
- [ ] 95. Implement find_stale_directories() with age filtering
- [ ] 96. Add vacuum CLI command and automatic startup execution
- [ ] 97. Implement BootstrapCommand class
- [ ] 98. Add validate_runtime_dependencies() for jq/yq checking
- [ ] 99. Implement extract_all_scripts() with AOT extraction
- [ ] 100. Add context file writing for scripts with context_data
- [ ] 101. Generate runtime_manifest.json for stage-executor.sh
- [ ] 102. Implement bootstrap CLI command with lock file validation
- [ ] 103. Write integration tests for bootstrap preparation
- [ ] 104. **CHECKPOINT 10: Bootstrap Preparation Functional**
  - **Deliverable**: Bootstrap command with dependency validation and script extraction
  - **Verification Criteria**:
    - `ztc bootstrap` validates jq/yq presence before execution
    - Scripts extracted to secure temp directory with 0700 permissions
    - Context files written for scripts with context_data
    - runtime_manifest.json maps stage names to script paths
    - Vacuum command cleans stale directories older than 60 minutes
  - **Test Script**: Run `poetry run pytest tests/integration/test_bootstrap_prep.py` to validate dependency checks, script extraction, and vacuum functionality
  - **Success Criteria**: Dependencies validated, scripts extracted securely, context files generated, vacuum removes stale dirs

## Phase 11: Eject Workflow Implementation

- [ ] 105. Create EjectWorkflow class (ztc/workflows/eject.py)
- [ ] 106. Implement validate_prerequisites() checking platform.yaml and artifacts
- [ ] 107. Add create_directory_structure() for output organization
- [ ] 108. Implement extract_adapter_scripts() with context files
- [ ] 109. Add copy_pipeline_yaml() to output directory
- [ ] 110. Implement generate_execution_guide() with README generation
- [ ] 111. Add display_summary() with Rich table output
- [ ] 112. Create eject CLI command with --env and --output flags
- [ ] 113. Write integration tests for eject workflow
- [ ] 114. **CHECKPOINT 11: Eject Command Functional**
  - **Deliverable**: Eject command extracting scripts and pipeline for manual debugging
  - **Verification Criteria**:
    - `ztc eject` extracts all scripts to debug directory
    - Context files written alongside scripts
    - pipeline.yaml copied to output directory
    - README.md generated with execution instructions
    - Scripts executable (0755 permissions)
  - **Test Script**: Run `poetry run pytest tests/integration/test_eject_workflow.py` to validate script extraction, context file generation, and README creation
  - **Success Criteria**: All scripts extracted, context files present, README provides clear instructions, directory structure matches spec

## Phase 12: Lock File & Validation

- [ ] 115. Implement LockFileGenerator class
- [ ] 116. Add generate() method creating lock file structure
- [ ] 117. Implement hash_directory() with streaming for large files
- [ ] 118. Add generate_adapter_metadata() for adapter versioning
- [ ] 119. Create validate CLI command
- [ ] 120. Implement lock file validation against platform.yaml hash
- [ ] 121. Add artifact hash validation
- [ ] 122. Write unit tests for lock file generation and validation
- [ ] 123. **CHECKPOINT 12: Lock File System Functional**
  - **Deliverable**: Lock file generation and validation preventing drift
  - **Verification Criteria**:
    - lock.json generated after successful render
    - Lock file contains platform_hash, artifacts_hash, adapter metadata
    - `ztc validate` detects platform.yaml modifications
    - `ztc validate` detects artifact modifications
    - Streaming hash handles large files without memory issues
  - **Test Script**: Run `poetry run pytest tests/integration/test_lock_file.py` to validate lock generation, hash calculation, and drift detection
  - **Success Criteria**: Lock file generated correctly, validation detects all modifications, streaming hash works for large files

## Phase 13: Error Handling & User Experience

- [ ] 124. Implement ZTCError base exception class
- [ ] 125. Add MissingCapabilityError with helpful messages
- [ ] 126. Add LockFileValidationError with remediation hints
- [ ] 127. Add RuntimeDependencyError for missing tools
- [ ] 128. Implement error handling in CLI commands with Rich formatting
- [ ] 129. Add progress indicators for long operations
- [ ] 130. Implement version CLI command displaying adapter versions
- [ ] 131. Write tests for error handling and user messaging
- [ ] 132. **CHECKPOINT 13: Error Handling Complete**
  - **Deliverable**: Comprehensive error handling with actionable user guidance
  - **Verification Criteria**:
    - All custom exceptions include help_text with remediation steps
    - CLI commands catch exceptions and display formatted errors
    - Progress bars shown for render and bootstrap operations
    - `ztc version` displays CLI and adapter versions
  - **Test Script**: Run `poetry run pytest tests/integration/test_error_handling.py` to validate error messages, help text, and user guidance
  - **Success Criteria**: All errors provide clear guidance, progress indicators work, version command displays correct info

## Phase 14: End-to-End Integration Testing

- [ ] 133. Create end-to-end test with full workflow (init → render → validate → eject)
- [ ] 134. Add test for resume functionality in init workflow
- [ ] 135. Test partial render with --partial flag
- [ ] 136. Validate debug mode preserves workspace on failure
- [ ] 137. Test vacuum command removes only stale directories
- [ ] 138. Validate version fallback behavior with network timeout
- [ ] 139. Test capability validation across all adapters
- [ ] 140. Validate context file usage in scripts
- [ ] 141. **CHECKPOINT 14: End-to-End Integration Validated**
  - **Deliverable**: Complete ZTC workflow tested from init to eject
  - **Verification Criteria**:
    - Full workflow (init → render → validate → eject) completes successfully
    - Resume functionality preserves existing config
    - Partial render only executes specified adapters
    - Debug mode preserves workspace for inspection
    - All 3 adapters integrate correctly with capability system
  - **Test Script**: Run `poetry run pytest tests/integration/test_end_to_end.py` to validate complete workflow with all commands
  - **Success Criteria**: All commands work together, workflow completes successfully, artifacts validate, eject produces usable debug output

## Phase 15: Documentation & Packaging

- [ ] 142. Create README.md with installation and usage instructions
- [ ] 143. Document adapter development guide
- [ ] 144. Add CLI command reference documentation
- [ ] 145. Create troubleshooting guide
- [ ] 146. Configure Poetry for binary distribution
- [ ] 147. Test PyInstaller packaging for standalone binary
- [ ] 148. Validate embedded resources in packaged binary
- [ ] 149. Create release workflow documentation
- [ ] 150. **CHECKPOINT 15: Project Complete & Documented**
  - **Deliverable**: Fully documented and packaged ZTC CLI
  - **Verification Criteria**:
    - README provides clear installation and usage instructions
    - Adapter development guide enables creating new adapters
    - CLI reference documents all commands and flags
    - PyInstaller produces working standalone binary
    - All embedded resources (adapters, scripts, templates) accessible in binary
  - **Test Script**: Run `poetry run pytest tests/packaging/test_binary_distribution.py` to validate packaged binary functionality
  - **Success Criteria**: Documentation complete, binary packages successfully, all features work in packaged binary
