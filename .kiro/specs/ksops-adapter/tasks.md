# KSOPS Adapter Implementation Tasks

## Task List

### Phase 1: Core Adapter Infrastructure

- [ ] 1. Create adapter package structure
  - Create `ztc/adapters/ksops/` directory
  - Create `__init__.py`, `adapter.py`, `config.py` files
  - Create `adapter.yaml` metadata file
  - Create `scripts/` and `templates/` directories

- [ ] 2. Implement KSOPSConfig Pydantic model
  - Define S3 configuration fields with SecretStr for secrets
  - Define tenant configuration fields
  - Add field validators for PEM format and patterns
  - Implement config validation tests

- [ ] 3. Implement KSOPSOutputData model
  - Define output data fields (non-sensitive only)
  - Add SecretStr rejection validator
  - Configure extra="forbid" to prevent unknown fields

- [ ] 4. **CHECKPOINT 1: Configuration Models Validated**
  - **Deliverable**: KSOPSConfig and KSOPSOutputData models with validation
  - **Verification Criteria**:
    - Valid configurations pass validation
    - Invalid configurations raise ValidationError with field details
    - SecretStr fields mask values in logs
    - Output model rejects SecretStr types
  - **Test Script**: Run unit tests in `zerotouch-engine/tests/unit/adapters/test_ksops_config.py`
  - **Success Criteria**: All config validation tests pass, secrets properly masked

### Phase 2: Script Extraction and Adaptation

- [ ] 5. Extract shared helper scripts
  - Copy `s3-helpers.sh` from zerotouch-platform to `scripts/shared/`
  - Copy `env-helpers.sh` from zerotouch-platform to `scripts/shared/`
  - Add META_REQUIRE headers to document dependencies
  - Note: These helpers will be inlined into scripts via `# INCLUDE:` markers during get_embedded_script() execution

- [ ] 6. Extract and adapt bootstrap scripts
  - Copy 8 bootstrap scripts from zerotouch-platform
  - Replace CLI argument parsing with context file reading
  - Replace secret reading from JSON with environment variable reading
  - Add `# INCLUDE:` markers for shared helpers
  - Add META_REQUIRE headers for context fields

- [ ] 7. Extract and adapt post-work scripts
  - Copy `09c-wait-ksops-sidecar.sh` from zerotouch-platform
  - Adapt to use context file for timeout configuration

- [ ] 8. Extract and adapt validation scripts
  - Copy 7 validation scripts from zerotouch-platform
  - Adapt to use hybrid context/env pattern
  - Add META_REQUIRE headers
  - Note: Scripts with `# INCLUDE:` markers will have helpers inlined during get_embedded_script() execution, not at copy time

- [ ] 9. **CHECKPOINT 2: Scripts Extracted and Adapted**
  - **Deliverable**: All 22 scripts extracted with context file adaptation
  - **Verification Criteria**:
    - Scripts read configuration from context JSON
    - Scripts read secrets from environment variables
    - META_REQUIRE headers match context_data fields
    - Shared helpers properly marked with # INCLUDE
  - **Test Script**: Run script contract validation in `zerotouch-engine/tests/unit/adapters/test_ksops_scripts.py`
  - **Success Criteria**: All scripts pass contract validation, no secrets in context files

### Phase 3: Template Extraction and Rendering

- [ ] 10. Extract YAML templates
  - Copy 5 YAML templates from zerotouch-platform to `templates/`
  - Convert to Jinja2 templates (.j2 extension)
  - Replace hardcoded values with template variables

- [ ] 11. Create .sops.yaml template
  - Create `.sops.yaml.j2` template for user-facing SOPS config
  - Add age_public_key variable placeholder
  - Add creation_rules for encrypted_regex pattern

- [ ] 12. Implement template rendering in adapter
  - Add template rendering logic to render() method
  - Configure Jinja2 environment with template directory
  - Generate manifests with age_public_key context

- [ ] 13. **CHECKPOINT 3: Templates Rendered**
  - **Deliverable**: 6 templates rendered with Age public key
  - **Verification Criteria**:
    - All templates render without errors
    - Age public key properly injected
    - .sops.yaml generated for repo root
    - Manifests output to platform/generated/ksops/
  - **Test Script**: Run template rendering tests in `zerotouch-engine/tests/unit/adapters/test_ksops_templates.py`
  - **Success Criteria**: All templates render correctly, .sops.yaml valid YAML

### Phase 4: Adapter Lifecycle Implementation

- [ ] 14. Implement get_required_inputs()
  - Define 10 InputPrompt objects for configuration
  - Set appropriate types (password, string, integer)
  - Add help text and defaults

- [ ] 15. Implement script reference methods
  - Implement bootstrap_scripts() with 8 ScriptReference objects
  - Implement post_work_scripts() with 1 ScriptReference
  - Implement validation_scripts() with 7 ScriptReference objects
  - Configure context_data and secret_env_vars correctly

- [ ] 16. Implement render() method
  - Validate kubernetes-api capability dependency
  - Retrieve Age public key
  - Create SecretsManagementCapability with public key
  - Create KSOPSOutputData
  - Return AdapterOutput with manifests and capabilities

- [ ] 17. Implement check_health() method
  - Add localized boto3 import
  - Implement S3 connectivity check
  - Add error handling with PreFlightError

- [ ] 18. **CHECKPOINT 4: Adapter Lifecycle Complete**
  - **Deliverable**: Full adapter lifecycle implementation
  - **Verification Criteria**:
    - All abstract methods implemented
    - Script references validate at instantiation
    - render() returns valid AdapterOutput
    - check_health() validates S3 connectivity
  - **Test Script**: Run adapter lifecycle tests in `zerotouch-engine/tests/integration/adapters/test_ksops_lifecycle.py`
  - **Success Criteria**: Adapter instantiates, renders manifests, validates dependencies

### Phase 5: CLI Extension Implementation

- [ ] 19. Implement CLI category method
  - Add static get_cli_category() returning "secret"
  - Ensure method is static for lazy loading

- [ ] 20. Implement CLI command handlers
  - Implement init_secrets_command()
  - Implement init_service_secrets_command()
  - Implement generate_secrets_command()
  - Implement create_dot_env_command()
  - Implement display_age_private_key_command()
  - Implement encrypt_secret_command()
  - Implement inject_offline_key_command()
  - Implement recover_command()
  - Implement rotate_keys_command()

- [ ] 21. Implement get_cli_app() method
  - Create Typer app
  - Register all 9 commands
  - Add command descriptions and help text

- [ ] 22. **CHECKPOINT 5: CLI Commands Functional**
  - **Deliverable**: 9 CLI commands under `ztc secret` namespace
  - **Verification Criteria**:
    - All commands registered under "secret" category
    - Commands execute scripts with correct context
    - Secrets passed via environment variables
    - Command output displays results correctly
  - **Test Script**: Run CLI integration tests in `zerotouch-engine/tests/integration/cli/test_secret_commands.py`
  - **Success Criteria**: All commands execute successfully, no secrets in logs

### Phase 6: Integration and End-to-End Validation

- [ ] 23. Register adapter in adapter registry
  - Add KSOPS adapter to registry discovery
  - Verify adapter.yaml metadata loaded correctly
  - Test adapter selection in platform.yaml

- [ ] 24. Implement capability contract
  - Add SecretsManagementCapability to capabilities.py
  - Include age_public_key field
  - Add encryption_env property helper

- [ ] 25. Test downstream adapter integration
  - Create mock downstream adapter consuming secrets capability
  - Verify age_public_key accessible from capability
  - Test encryption using public key

- [ ] 26. **CHECKPOINT 6: Full Integration Validated**
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

### Phase 7: Property-Based Testing

- [ ] 27. Implement Property 1: Configuration Validation Completeness
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
  - Verify bootstrap_scripts() returns 8 references
  - Verify post_work_scripts() returns 1 reference
  - Verify validation_scripts() returns 7 references

- [ ] 31. Implement Property 7-8: Context Data Validation
  - Verify context_data JSON-serializable
  - Verify no null or empty values in context_data

- [ ] 32. Implement Property 9-10: Capability Contract
  - Verify render() with kubernetes-api returns secrets-management capability
  - Verify render() without kubernetes-api raises ValueError

- [ ] 33. Implement Property 11-12: Metadata and Enum Validation
  - Verify load_metadata() returns all required fields
  - Verify all KSOPSScripts enum values map to existing files

- [ ] 34. **CHECKPOINT 7: Property-Based Tests Pass**
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
