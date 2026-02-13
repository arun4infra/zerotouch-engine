# Task List: ZTC Phase 1 - Multi-Adapter Foundation

## Phase 1: Project Setup & Core Infrastructure

- [x] 1. Initialize ZTC project structure with Poetry
- [x] 2. Set up Python package structure (ztc/ directory)
- [x] 3. Configure pyproject.toml with dependencies (Typer, Rich, Pydantic, Jinja2, PyYAML)
- [x] 4. Create base directory structure for adapters, templates, and scripts
- [x] 5. Set up pytest configuration and test directory structure
- [*] 6. **CHECKPOINT 1: Project Foundation Ready**
  - **Deliverable**: ZTC project initialized with Poetry, all dependencies installed, directory structure created
  - **Verification Criteria**:
    - `poetry install` completes successfully
    - `poetry run python -c "import typer, rich, pydantic, jinja2, yaml"` succeeds
    - Directory structure matches design spec (ztc/adapters/, ztc/cli.py, tests/)
  - **Test Script**: Run `poetry run pytest tests/test_project_setup.py` to validate package imports and directory structure
  - **Success Criteria**: All dependencies importable, project structure validated, pytest runs successfully

## Phase 2: Capability Interface & Base Adapter Contract

- [x] 7. Implement Capability enum and Pydantic models (ztc/interfaces/capabilities.py)
- [x] 8. Create CAPABILITY_CONTRACTS registry binding enums to models
- [x] 9. Implement PlatformAdapter abstract base class (ztc/adapters/base.py)
- [x] 10. Add InputPrompt, ScriptReference, PipelineStage, AdapterOutput dataclasses
- [x] 11. Implement ScriptReference.__post_init__ with static validation
- [x] 12. Create AdapterRegistry class for adapter discovery and loading
- [x] 13. Write unit tests for capability contracts and base adapter interface
- [x] 14. **CHECKPOINT 2: Adapter Contract Established**
  - **Deliverable**: Type-safe capability system and adapter base class with validation
  - **Verification Criteria**:
    - All Capability enums map to Pydantic models in CAPABILITY_CONTRACTS
    - PlatformAdapter abstract methods defined (get_required_inputs, pre_work_scripts, bootstrap_scripts, post_work_scripts, validation_scripts, render)
    - ScriptReference validates script existence at instantiation
  - **Test Script**: Run `poetry run pytest tests/unit/test_adapter_contract.py` to validate capability contracts, adapter interface, and script validation
  - **Success Criteria**: All capability models validate correctly, adapter interface enforces contracts, script validation catches missing resources

## Phase 3: Hetzner Adapter Implementation

- [x] 15. Create Hetzner adapter directory structure (ztc/adapters/hetzner/ with pre_work/, bootstrap/, post_work/, validation/ folders)
- [x] 16. Implement HetznerConfig Pydantic model with validation
- [x] 17. Create adapter.yaml metadata file for Hetzner
- [x] 18. Implement HetznerAdapter class with get_required_inputs()
- [x] 19. Implement HetznerAdapter.render() with async Hetzner API calls (server ID lookup, metadata queries)
- [x] 20. Add CloudInfrastructureCapability output to render() (provider, server_ids, region)
- [x] 21. Write unit tests for Hetzner adapter configuration and rendering
- [x] 22. **CHECKPOINT 3: Hetzner Adapter Functional**
  - **Deliverable**: Hetzner adapter with API integration and capability output
  - **Verification Criteria**:
    - HetznerAdapter validates config via Pydantic model
    - render() method queries Hetzner API and returns server metadata
    - CloudInfrastructureCapability output includes provider, server_ids, region
    - Adapter follows standard folder structure (pre_work/, bootstrap/, post_work/, validation/ folders exist even if empty)
    - No bash scripts required (pure Python API integration)
  - **Test Script**: Run `poetry run pytest tests/integration/test_hetzner_adapter.py` to validate Hetzner API integration (mocked), config validation, and capability output
  - **Success Criteria**: Adapter renders successfully with mocked API, capability data validates against contract, folder structure is standard

## Phase 4: Cilium Adapter Implementation

- [x] 23. Create Cilium adapter directory structure (ztc/adapters/cilium/ with pre_work/, bootstrap/, post_work/, validation/ folders)
- [x] 24. Implement CiliumConfig Pydantic model
- [x] 25. Create adapter.yaml metadata with capability requirements (kubernetes-api)
- [x] 26. Implement CiliumAdapter class with BGP configuration support
- [x] 27. Create Jinja2 templates (manifests.yaml.j2)
- [x] 28. Extract and adapt wait-cilium.sh from zerotouch-platform/scripts/bootstrap/wait/06-wait-cilium.sh to bootstrap/wait-cilium.sh (inline kubectl_retry function)
- [x] 29. Extract and adapt wait-gateway-api.sh from zerotouch-platform/scripts/bootstrap/wait/06a-wait-gateway-api.sh to bootstrap/wait-gateway-api.sh (Gateway API CRD validation)
- [x] 30. Extract and adapt validate-cni.sh from zerotouch-platform/scripts/bootstrap/validation/ to validation/validate-cni.sh (pod networking verification)
- [x] 31. Implement CiliumAdapter.render() with template rendering
- [x] 32. Add CNIArtifacts and GatewayAPICapability outputs
- [x] 33. Implement get_invalid_fields() for differential validation
- [x] 34. Write unit tests for Cilium adapter and template rendering
- [x] 35. **CHECKPOINT 4: Cilium Adapter Functional**
  - **Deliverable**: Cilium adapter with template rendering and capability outputs
  - **Verification Criteria**:
    - CiliumAdapter renders manifests via Jinja2 templates
    - CNIArtifacts capability includes manifests content
    - GatewayAPICapability indicates CRDs embedded
    - Differential validation detects OS changes
    - Scripts follow standard folder structure (pre_work/, bootstrap/, post_work/, validation/)
    - Bootstrap scripts (wait-cilium.sh, wait-gateway-api.sh) are core CNI readiness logic
    - Scripts extracted from zerotouch-platform with inline utility functions
  - **Test Script**: Run `poetry run pytest tests/integration/test_cilium_adapter.py` to validate template rendering, capability outputs, validation logic, and extracted scripts
  - **Success Criteria**: Templates render correctly, capability data validates, differential validation works, scripts use context files, folder structure is standard

## Phase 5: Talos Adapter Implementation

- [x] 36. Create Talos adapter directory structure (ztc/adapters/talos/ with pre_work/, bootstrap/, post_work/, validation/ folders)
- [x] 37. Implement TalosConfig and NodeConfig Pydantic models
- [x] 38. Create TalosScripts enum for static validation
- [x] 39. Create adapter.yaml metadata with capability provides/requires
- [x] 40. Implement TalosAdapter class with node configuration
- [x] 41. Create Jinja2 templates (controlplane.yaml.j2, worker.yaml.j2, talosconfig.j2)
- [x] 42. Extract and adapt enable-rescue-mode.sh from zerotouch-platform/scripts/bootstrap/00-enable-rescue-mode.sh to pre_work/enable-rescue-mode.sh (inline Hetzner API functions from helpers/hetzner-api.sh, convert CLI args to context_data)
- [x] 43. Extract and adapt 02-embed-network-manifests.sh from zerotouch-platform/scripts/bootstrap/install/02-embed-network-manifests.sh to bootstrap/embed-network-manifests.sh (manifest embedding logic)
- [x] 44. Extract and adapt 03-install-talos.sh from zerotouch-platform/scripts/bootstrap/install/03-install-talos.sh to bootstrap/install-talos.sh (convert CLI args to context_data, remove sshpass dependency by using context)
- [x] 45. Extract and adapt 04-bootstrap-talos.sh from zerotouch-platform/scripts/bootstrap/install/04-bootstrap-talos.sh to bootstrap/bootstrap-talos.sh (remove OIDC patch logic, use base config)
- [x] 46. Extract and adapt 05-add-worker-nodes.sh from zerotouch-platform/scripts/bootstrap/install/05-add-worker-nodes.sh to bootstrap/add-worker-nodes.sh (worker addition logic with context_data)
- [x] 47. Extract and adapt validate-cluster.sh from zerotouch-platform/scripts/bootstrap/validation/99-validate-cluster.sh to validation/validate-cluster.sh (node join verification)
- [x] 48. Implement TalosAdapter.render() with per-node config generation
- [x] 49. Add KubernetesAPICapability output
- [x] 50. Write unit tests for Talos adapter and multi-node rendering
- [x] 51. **CHECKPOINT 5: Talos Adapter Functional**
  - **Deliverable**: Talos adapter with multi-node config generation and capability output
  - **Verification Criteria**:
    - TalosAdapter renders separate configs for controlplane and worker nodes
    - KubernetesAPICapability includes cluster_endpoint and kubeconfig_path
    - Pre-work script (enable-rescue-mode.sh) has inlined Hetzner API functions (no external dependencies)
    - Bootstrap scripts (install-talos.sh, bootstrap-talos.sh, add-worker-nodes.sh) are core OS installation logic
    - All scripts follow standard folder structure (pre_work/, bootstrap/, post_work/, validation/)
    - All scripts extracted from zerotouch-platform and adapted to use context_data
    - Templates embed CNI manifests from upstream capability
    - All scripts read context via $ZTC_CONTEXT_FILE (no CLI args)
    - Adapter is fully self-contained with no cross-adapter dependencies
  - **Test Script**: Run `poetry run pytest tests/integration/test_talos_adapter.py` to validate multi-node rendering, capability integration, context file generation, script independence, folder structure, and extracted scripts
  - **Success Criteria**: Node configs render correctly, capability data validates, context files generated for scripts, scripts use jq to read context, pre-work script is self-contained, folder structure is standard

## Phase 6: CLI Framework & Init Workflow

- [x] 52. Implement CLI app structure with Typer (ztc/cli.py)
- [x] 53. Create SelectionGroup dataclass for dynamic UI grouping
- [x] 54. Implement build_selection_groups() for registry-driven UI
- [x] 55. Create InitWorkflow class with progressive input collection
- [x] 56. Implement handle_group_selection() with conflict cleanup
- [x] 57. Implement collect_adapter_inputs() with Pydantic validation
- [x] 58. Implement validate_downstream_adapters() with differential validation
- [x] 59. Add display_summary() with Rich table output
- [x] 60. Implement platform.yaml generation and writing
- [x] 61. Add --resume flag support for resuming configuration
- [x] 62. Write integration tests for init workflow with mocked prompts
- [x] 63. **CHECKPOINT 6: Init Command Functional**
  - **Deliverable**: Interactive CLI wizard generating platform.yaml
  - **Verification Criteria**:
    - `ztc init` prompts for cloud provider, network, OS selections
    - Adapter-specific inputs collected with validation
    - platform.yaml generated with correct structure
    - --resume flag loads existing config and skips completed sections
  - **Test Script**: Run `poetry run pytest tests/integration/test_init_workflow.py` with mocked prompts to validate full init flow and platform.yaml generation
  - **Success Criteria**: Init workflow completes, platform.yaml validates against schema, resume functionality works

## Phase 7: Version Registry & Remote Fetch

- [x] 64. Create embedded versions.yaml with component versions
- [x] 65. Implement VersionRegistry class with embedded version loading
- [x] 66. Add start_background_fetch() for async remote version fetch
- [x] 67. Implement get_versions_async() with explicit await and timeout
- [x] 68. Add version source tracking (_version_source field)
- [x] 69. Implement _fetch_remote_async() with signature verification
- [x] 70. Add get_version_source() for user transparency
- [x] 71. Integrate version registry into init workflow with user notification
- [x] 72. Write unit tests for version fetching and fallback behavior
- [x] 73. **CHECKPOINT 7: Version Management Functional**
  - **Deliverable**: Version registry with remote fetch and explicit user notification
  - **Verification Criteria**:
    - Embedded versions.yaml loads successfully
    - Remote fetch attempts with timeout (2s default)
    - User notified of version source (remote vs embedded)
    - Fallback to embedded versions on timeout/error
  - **Test Script**: Run `poetry run pytest tests/unit/test_version_registry.py` to validate version loading, remote fetch with mocked network, and fallback behavior
  - **Success Criteria**: Version registry loads embedded versions, remote fetch works with mocks, user notification displays correct source

## Phase 8: Engine & Dependency Resolution

- [x] 74. Implement PlatformEngine class (ztc/engine.py)
- [x] 75. Create shared Jinja2 environment with PrefixLoader
- [x] 76. Implement _create_shared_jinja_env() with adapter namespacing
- [x] 77. Create ContextSnapshot class for immutable context
- [x] 78. Implement PlatformContext class for mutable engine state
- [x] 79. Add get_capability_data() with enum-based type-safe access
- [x] 80. Implement DependencyResolver with topological sort
- [x] 81. Add capability registry building and validation
- [x] 82. Implement resolve_adapters() with phase grouping
- [x] 83. Write unit tests for dependency resolution and capability validation
- [x] 84. **CHECKPOINT 8: Engine Core Functional**
  - **Deliverable**: Engine with dependency resolution and capability management
  - **Verification Criteria**:
    - Shared Jinja environment created with adapter prefixes
    - Dependency resolver orders adapters correctly (Hetzner → Talos → Cilium)
    - Capability registry validates requirements against providers
    - ContextSnapshot provides immutable read-only access
  - **Test Script**: Run `poetry run pytest tests/unit/test_engine_core.py` to validate dependency resolution, capability validation, and context management
  - **Success Criteria**: Adapters resolve in correct order, capability contracts enforced, context immutability maintained

## Phase 9: Render Pipeline Implementation

- [x] 85. Implement Engine.render() async method
- [x] 86. Add workspace creation and cleanup logic
- [x] 87. Implement adapter rendering loop with context snapshots
- [x] 88. Add write_adapter_output() for manifest writing
- [x] 89. Implement generate_pipeline_yaml() from adapter stages
- [x] 90. Add write_debug_scripts() for observability
- [x] 91. Implement validate_artifacts() against output schemas
- [x] 92. Add atomic_swap_generated() for atomic directory replacement
- [x] 93. Implement lock file generation with artifact hashing
- [x] 94. Add streaming file hashing (hash_file with chunks)
- [x] 95. Create render CLI command with --debug and --partial flags
- [x] 96. Write integration tests for full render pipeline
- [x] 97. **CHECKPOINT 9: Render Pipeline Functional**
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

- [x] 98. Implement SecureTempDir context manager with signal handling
- [x] 99. Add _signal_handler() for SIGINT/SIGTERM cleanup
- [x] 100. Create VacuumCommand for stale temp directory cleanup
- [x] 101. Implement find_stale_directories() with age filtering
- [x] 102. Add vacuum CLI command and automatic startup execution
- [x] 103. Implement BootstrapCommand class
- [x] 104. Add validate_runtime_dependencies() for jq/yq checking
- [x] 105. Implement extract_all_scripts() with AOT extraction
- [x] 106. Add context file writing for scripts with context_data
- [x] 107. Generate runtime_manifest.json for stage-executor.sh
- [x] 108. Implement bootstrap CLI command with lock file validation
- [x] 109. Write integration tests for bootstrap preparation
- [x] 110. **CHECKPOINT 10: Bootstrap Preparation Functional**
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

- [x] 111. Create EjectWorkflow class (ztc/workflows/eject.py)
- [x] 112. Implement validate_prerequisites() checking platform.yaml and artifacts
- [x] 113. Add create_directory_structure() for output organization
- [x] 114. Implement extract_adapter_scripts() with context files
- [x] 115. Add copy_pipeline_yaml() to output directory
- [x] 116. Implement generate_execution_guide() with README generation
- [x] 117. Add display_summary() with Rich table output
- [x] 118. Create eject CLI command with --env and --output flags
- [x] 119. Write integration tests for eject workflow
- [x] 120. **CHECKPOINT 11: Eject Command Functional**
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

- [x] 121. Implement LockFileGenerator class
- [x] 122. Add generate() method creating lock file structure
- [x] 123. Implement hash_directory() with streaming for large files
- [x] 124. Add generate_adapter_metadata() for adapter versioning
- [x] 125. Create validate CLI command
- [x] 126. Implement lock file validation against platform.yaml hash
- [x] 127. Add artifact hash validation
- [x] 128. Write unit tests for lock file generation and validation
- [x] 129. **CHECKPOINT 12: Lock File System Functional**
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

- [x] 130. Implement ZTCError base exception class
- [x] 131. Add MissingCapabilityError with helpful messages
- [x] 132. Add LockFileValidationError with remediation hints
- [x] 133. Add RuntimeDependencyError for missing tools
- [x] 134. Implement error handling in CLI commands with Rich formatting
- [x] 135. Add progress indicators for long operations
- [x] 136. Implement version CLI command displaying adapter versions
- [x] 137. Write tests for error handling and user messaging
- [x] 138. **CHECKPOINT 13: Error Handling Complete**
  - **Deliverable**: Comprehensive error handling with actionable user guidance
  - **Verification Criteria**:
    - All custom exceptions include help_text with remediation steps
    - CLI commands catch exceptions and display formatted errors
    - Progress bars shown for render and bootstrap operations
    - `ztc version` displays CLI and adapter versions
  - **Test Script**: Run `poetry run pytest tests/integration/test_error_handling.py` to validate error messages, help text, and user guidance
  - **Success Criteria**: All errors provide clear guidance, progress indicators work, version command displays correct info

## Phase 14: End-to-End Integration Testing

- [x] 139. Create end-to-end test with full workflow (init → render → validate → eject)
- [x] 140. Add test for resume functionality in init workflow
- [x] 141. Test partial render with --partial flag
- [x] 142. Validate debug mode preserves workspace on failure
- [x] 143. Test vacuum command removes only stale directories
- [x] 144. Validate version fallback behavior with network timeout
- [x] 145. Test capability validation across all adapters
- [x] 146. Validate context file usage in scripts
- [x] 147. **CHECKPOINT 14: End-to-End Integration Validated**
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

- [x] 148. Create README.md with installation and usage instructions
- [x] 149. Document adapter development guide
- [x] 150. Add CLI command reference documentation
- [x] 151. Create troubleshooting guide
- [x] 152. Configure Poetry for binary distribution
- [x] 153. Test PyInstaller packaging for standalone binary
- [x] 154. Validate embedded resources in packaged binary
- [x] 155. Create release workflow documentation
- [x] 156. **CHECKPOINT 15: Project Complete & Documented**
  - **Deliverable**: Fully documented and packaged ZTC CLI
  - **Verification Criteria**:
    - README provides clear installation and usage instructions
    - Adapter development guide enables creating new adapters
    - CLI reference documents all commands and flags
    - PyInstaller produces working standalone binary
    - All embedded resources (adapters, scripts, templates) accessible in binary
  - **Test Script**: Run `poetry run pytest tests/packaging/test_binary_distribution.py` to validate packaged binary functionality
  - **Success Criteria**: Documentation complete, binary packages successfully, all features work in packaged binary
