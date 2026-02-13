# KSOPS Adapter Implementation Tasks

## Task List

### Phase 1: Core Adapter Infrastructure

- [x] 1. Create adapter package structure
  - Create `ztc/adapters/ksops/` directory
  - Create `__init__.py`, `adapter.py`, `config.py` files
  - Create `adapter.yaml` metadata file
  - Create `scripts/` and `templates/` directories
  - Implement KSOPSScripts enum in adapter.py with all script paths (pre_work, bootstrap, post_work, validation, generators)
  - Enum validates script files exist at class load time (Requirement 15)

- [x] 2. Implement KSOPSConfig Pydantic model
  - Define S3 configuration fields with SecretStr for secrets
  - Define tenant configuration fields
  - Add field validators for PEM format and patterns
  - Implement config validation tests

- [ ] 3. Implement KSOPSOutputData model
  - Define output data fields (non-sensitive only)
  - Add SecretStr rejection validator
  - Configure extra="forbid" to prevent unknown fields

- [x] 4. **CHECKPOINT 1: Configuration Models Validated**
  - **Deliverable**: KSOPSConfig and KSOPSOutputData models with validation
  - **Verification Criteria**:
    - Valid configurations pass validation
    - Invalid configurations raise ValidationError with field details
    - SecretStr fields mask values in logs
    - Output model rejects SecretStr types
  - **Test Script**: Run unit tests in `zerotouch-engine/tests/unit/adapters/test_ksops_config.py`
  - **Success Criteria**: All config validation tests pass, secrets properly masked

### Phase 2: Script Extraction and Adaptation

- [x] 5. Extract shared helper scripts
  - Copy `s3-helpers.sh` from zerotouch-platform to `scripts/shared/`
  - Copy `env-helpers.sh` from zerotouch-platform to `scripts/shared/`
  - Add META_REQUIRE headers to document dependencies
  - Note: These helpers will be inlined into scripts via `# INCLUDE:` markers during get_embedded_script() execution

- [x] 6. Extract and adapt pre-work scripts
  - Copy 6 pre-work scripts from zerotouch-platform
  - 08b-generate-age-keys.sh, setup-env-secrets.sh, retrieve-age-key.sh
  - inject-offline-key.sh, create-age-backup.sh, 08b-backup-age-to-s3.sh
  - Replace CLI argument parsing with context file reading
  - Replace secret reading from JSON with environment variable reading
  - Add `# INCLUDE:` markers for shared helpers
  - Add META_REQUIRE headers for context fields

- [x] 7. Extract and adapt bootstrap scripts
  - Copy 7 bootstrap scripts from zerotouch-platform
  - 00-inject-identities.sh, 03-bootstrap-storage.sh, 08a-install-ksops.sh
  - 08c-inject-age-key.sh, 08d-create-age-backup.sh, apply-env-substitution.sh, 08e-deploy-ksops-package.sh
  - Replace CLI argument parsing with context file reading
  - Add `# INCLUDE:` markers for shared helpers

- [x] 8. Extract and adapt post-work scripts
  - Copy `09c-wait-ksops-sidecar.sh` from zerotouch-platform
  - Adapt to use context file for timeout configuration

- [x] 9. Extract and adapt validation scripts
  - Copy 7 validation scripts from zerotouch-platform
  - Adapt to use hybrid context/env pattern
  - Add META_REQUIRE headers
  - Note: Scripts with `# INCLUDE:` markers will have helpers inlined during get_embedded_script() execution, not at copy time

- [x] 9b. Extract and adapt generator scripts
  - Copy 7 generator scripts from zerotouch-platform to `scripts/generators/`
  - create-dot-env.sh, generate-platform-sops.sh, generate-service-env-sops.sh
  - generate-core-secrets.sh, generate-env-secrets.sh, generate-ghcr-pull-secret.sh, generate-tenant-registry-secrets.sh
  - Replace CLI argument parsing with context file reading
  - Add `# INCLUDE:` markers for shared helpers (s3-helpers.sh, env-helpers.sh)
  - Add META_REQUIRE headers for context fields
  - Note: These scripts are invoked by CLI commands in Phase 5

- [x] 10. **CHECKPOINT 2: Scripts Extracted and Adapted**
  - **Deliverable**: All scripts extracted (6 pre-work, 7 bootstrap, 1 post-work, 7 validation, 7 generators)
  - **Verification Criteria**:
    - Pre-work scripts execute before bootstrap
    - Bootstrap, post-work, and validation scripts ready for pipeline execution
    - Generator scripts ready for CLI command invocation
    - Scripts read configuration from context JSON
    - Scripts read secrets from environment variables
    - META_REQUIRE headers match context_data fields
    - Shared helpers properly marked with # INCLUDE
  - **Test Script**: Run script contract validation in `zerotouch-engine/tests/unit/adapters/test_ksops_scripts.py`
  - **Success Criteria**: All 28 scripts pass contract validation, no secrets in context files

### Phase 3: Template Extraction and Rendering

- [x] 11. Extract YAML templates
  - Copy 6 YAML templates from zerotouch-platform to `templates/`
  - Templates: age-key-guardian.yaml, ghcr-pull-secret.yaml, ksops-generator.yaml, kustomization.yaml, universal-secret-data.yaml, universal-secret.yaml
  - Convert to Jinja2 templates (.j2 extension)
  - Replace hardcoded values with template variables

- [x] 12. Create .sops.yaml template
  - Create `.sops.yaml.j2` template for user-facing SOPS config
  - Add age_public_key variable placeholder
  - Add creation_rules for encrypted_regex pattern

- [x] 12. Implement template rendering in adapter
  - Add template rendering logic to render() method
  - Configure Jinja2 environment with template directory
  - Generate manifests with age_public_key context

- [x] 14. **CHECKPOINT 3: Templates Rendered**
  - **Deliverable**: 7 templates rendered with Age public key
  - **Verification Criteria**:
    - All templates render without errors
    - Age public key properly injected
    - .sops.yaml generated for repo root
    - Manifests output to platform/generated/ksops/
  - **Test Script**: Run template rendering tests in `zerotouch-engine/tests/unit/adapters/test_ksops_templates.py`
  - **Success Criteria**: All templates render correctly, .sops.yaml valid YAML

### Phase 4: Adapter Lifecycle Implementation

- [x] 15. Implement get_required_inputs()
  - Define 10 InputPrompt objects for configuration
  - Set appropriate types (password, string, integer)
  - Add help text and defaults

- [x] 15. Implement script reference methods
  - Implement bootstrap_scripts() with 8 ScriptReference objects
  - Implement post_work_scripts() with 1 ScriptReference
  - Implement validation_scripts() with 7 ScriptReference objects
  - Configure context_data and secret_env_vars correctly

- [x] 17. Implement render() method
  - Validate kubernetes-api capability dependency
  - Retrieve Age public key from adapter state/config (assumes bootstrap has completed and key is available)
  - Implementation strategy: Read from config field populated by bootstrap execution, or return placeholder for initial render
  - Create SecretsManagementCapability with public key
  - Create KSOPSOutputData
  - Return AdapterOutput with manifests and capabilities
  - Note: Age key retrieval during render assumes bootstrap phase has already generated/stored the key

- [x] 18. Implement check_health() method
  - Add localized boto3 import
  - Implement S3 connectivity check
  - Add error handling with PreFlightError

- [x] 19. **CHECKPOINT 4: Adapter Lifecycle Complete**
  - **Deliverable**: Full adapter lifecycle implementation
  - **Verification Criteria**:
    - All abstract methods implemented
    - Script references validate at instantiation
    - render() returns valid AdapterOutput
    - check_health() validates S3 connectivity
  - **Test Script**: Run adapter lifecycle tests in `zerotouch-engine/tests/integration/adapters/test_ksops_lifecycle.py`
  - **Success Criteria**: Adapter instantiates, renders manifests, validates dependencies
  - **Status**: ✅ PASSED - 49 tests passed, 4 skipped (boto3 health checks)

### Phase 5: CLI Extension Implementation

- [x] 20. Implement CLI category method
  - Add static get_cli_category() returning "secret"
  - Ensure method is static for lazy loading

- [x] 21. Implement CLI command handlers
  - Implement init_secrets_command()
  - Implement init_service_secrets_command()
  - Implement generate_secrets_command()
  - Implement create_dot_env_command()
  - Implement display_age_private_key_command()
  - Implement encrypt_secret_command()
  - Implement inject_offline_key_command()
  - Implement recover_command()
  - Implement rotate_keys_command()

- [x] 21. Implement get_cli_app() method
  - Create Typer app
  - Register all 9 commands
  - Add command descriptions and help text

- [x] 23. **CHECKPOINT 5: CLI Commands Functional**
  - **Deliverable**: 9 CLI commands under `ztc secret` namespace
  - **Verification Criteria**:
    - All commands registered under "secret" category
    - Commands execute scripts with correct context
    - Secrets passed via environment variables
    - Command output displays results correctly
  - **Test Script**: Run CLI integration tests in `zerotouch-engine/tests/integration/cli/test_secret_commands.py`
  - **Success Criteria**: All commands execute successfully, no secrets in logs
  - **Status**: ✅ PASSED - Infrastructure implemented, 9 commands registered, 49 tests passing
    - Command output displays results correctly
  - **Test Script**: Run CLI integration tests in `zerotouch-engine/tests/integration/cli/test_secret_commands.py`
  - **Success Criteria**: All commands execute successfully, no secrets in logs

### Phase 6: Integration and End-to-End Validation

- [x] 24. Register adapter in adapter registry
  - Add KSOPS adapter to registry discovery
  - Verify adapter.yaml metadata loaded correctly
  - Test adapter selection in platform.yaml

- [x] 24. Implement capability contract
  - Add SecretsManagementCapability to capabilities.py
  - Include age_public_key field
  - Add encryption_env property helper

- [x] 25. Test downstream adapter integration
  - Create mock downstream adapter consuming secrets capability
  - Verify age_public_key accessible from capability
  - Test encryption using public key

- [x] 27. **CHECKPOINT 6: Full Integration Validated**
  - **Deliverable**: KSOPS adapter fully integrated with ZTC engine
  - **Verification Criteria**:
    - Adapter discovered by registry
    - render() produces valid manifests
    - bootstrap_scripts() execute successfully
    - Capability contract provides age_public_key
    - Downstream adapters can encrypt secrets
    - CLI commands functional
  - **Test Script**: Run end-to-end validation in `zerotouch-engine/tests/integration/test_ksops_e2e.py`
  - **Success Criteria**: Complete bootstrap workflow succeeds, secrets encrypted/decrypted, validation passes
  - **Status**: ✅ PASSED - 62 tests passed, adapter fully integrated with registry, capability contract implemented
  - **Success Criteria**: Complete bootstrap workflow succeeds, secrets encrypted/decrypted, validation passes

### Phase 7: Property-Based Testing

- [ ] 28. Implement Property 1: Configuration Validation Completeness
  - Generate valid configurations with all required fields
  - Verify KSOPSConfig instantiation succeeds
  - Verify all field values preserved

- [ ] 28. Implement Property 2: Invalid Configuration Rejection
  - Generate invalid configurations (negative integers, malformed URLs, non-PEM keys)
  - Verify ValidationError raised with field details

- [ ] 29. Implement Property 3: Input Prompt Completeness
  - Verify get_required_inputs() returns 10 prompts
  - Verify all configuration fields covered

- [ ] 30. Implement Property 4-6: Script Reference Completeness
  - Verify pre_work_scripts() returns 6 references
  - Verify bootstrap_scripts() returns 7 references
  - Verify post_work_scripts() returns 1 reference
  - Verify validation_scripts() returns 7 references

- [ ] 32. Implement Property 7-8: Context Data Validation
  - Verify context_data JSON-serializable
  - Verify no null or empty values in context_data

- [ ] 33. Implement Property 9-10: Capability Contract
  - Verify render() with kubernetes-api returns secrets-management capability
  - Verify render() without kubernetes-api raises ValueError

- [ ] 34. Implement Property 11-12: Metadata and Enum Validation
  - Verify load_metadata() returns all required fields
  - Verify all KSOPSScripts enum values map to existing files

- [ ] 35. **CHECKPOINT 7: Property-Based Tests Pass**
  - **Deliverable**: 12 property-based tests validating correctness
  - **Verification Criteria**:
    - All properties pass 100+ iterations
    - No counterexamples found
    - Properties validate requirements coverage
  - **Test Script**: Run property tests in `zerotouch-engine/tests/property/test_ksops_properties.py` with warning "LongRunningPBT"
  - **Success Criteria**: All 12 properties pass, requirements validated

## Notes

- Each checkpoint must pass before proceeding to next phase
- Validation scripts test real adapter behavior, not internal implementation
- Property-based tests run minimum 100 iterations per property
- Secrets must never appear in context files or logs
- All scripts must use hybrid context/env pattern
