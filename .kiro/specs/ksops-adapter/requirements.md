# Requirements Document

## Introduction

The KSOPS adapter integrates SOPS (Secrets OPerationS) with Age encryption into the ZeroTouch Composition Engine (ZTC). It follows the standard ZTC adapter pattern to provide secrets management capabilities through script extraction, context file generation, and capability-based dependency resolution.

## Glossary

- **KSOPS_Adapter**: ZTC adapter that provides secrets-management capability
- **Adapter_Metadata**: adapter.yaml file declaring capabilities, version, and selection group
- **Config_Model**: Pydantic model validating adapter configuration from platform.yaml
- **Script_Reference**: Pointer to embedded script with context data for execution
- **Context_File**: JSON file containing script parameters (replaces CLI arguments)
- **Capability**: Typed contract that adapters provide/require for dependency resolution
- **Pipeline_Stage**: Execution phase (pre_work, bootstrap, post_work, validation)
- **ZTC_Engine**: Core orchestration engine that resolves adapter dependencies and executes pipeline
- **Adapter_Registry**: Central registry that discovers and loads available adapters
- **Input_Prompt**: Interactive prompt definition for ztc init workflow

## Requirements

### Requirement 1: Adapter Directory Structure

**User Story:** As a ZTC engine, I want the KSOPS adapter to follow the standard directory structure, so that it integrates seamlessly with the adapter registry.

#### Acceptance Criteria

1. THE KSOPS_Adapter SHALL exist at path ztc/adapters/ksops/
2. THE KSOPS_Adapter SHALL contain an adapter.py file implementing the PlatformAdapter interface
3. THE KSOPS_Adapter SHALL contain an adapter.yaml file with metadata
4. THE KSOPS_Adapter SHALL contain a scripts/ directory with subdirectories: pre_work/, bootstrap/, post_work/, validation/
5. THE KSOPS_Adapter SHALL contain a templates/ directory for Jinja2 templates

### Requirement 2: Adapter Metadata Declaration

**User Story:** As a ZTC engine, I want adapter metadata declared in adapter.yaml, so that the registry can discover capabilities and dependencies.

#### Acceptance Criteria

1. THE Adapter_Metadata SHALL declare name as "ksops"
2. THE Adapter_Metadata SHALL declare phase as "secrets"
3. THE Adapter_Metadata SHALL declare selection_group as "secrets_management"
4. THE Adapter_Metadata SHALL declare provides capability as "secrets-management"
5. THE Adapter_Metadata SHALL declare requires capability as "kubernetes-api"
6. THE Adapter_Metadata SHALL declare supported_versions list
7. THE Adapter_Metadata SHALL declare default_version

### Requirement 3: Configuration Model Definition

**User Story:** As a platform operator, I want adapter configuration validated, so that invalid configurations are rejected before execution.

#### Acceptance Criteria

1. THE Config_Model SHALL define s3_access_key field as required string
2. THE Config_Model SHALL define s3_secret_key field as required string
3. THE Config_Model SHALL define s3_endpoint field as required string with URL validation
4. THE Config_Model SHALL define s3_region field as required string
5. THE Config_Model SHALL define s3_bucket_name field as required string
6. THE Config_Model SHALL define github_app_id field as required positive integer
7. THE Config_Model SHALL define github_app_installation_id field as required positive integer
8. THE Config_Model SHALL define github_app_private_key field as required string
9. THE Config_Model SHALL define tenant_org_name field as required string matching pattern ^[a-zA-Z0-9-]+$
10. THE Config_Model SHALL define tenant_repo_name field as required string matching pattern ^[a-zA-Z0-9-]+$

### Requirement 4: Interactive Input Prompts

**User Story:** As a platform operator, I want interactive prompts during ztc init, so that I can configure the KSOPS adapter without manually editing YAML.

#### Acceptance Criteria

1. THE KSOPS_Adapter SHALL return Input_Prompt for s3_access_key with type "password"
2. THE KSOPS_Adapter SHALL return Input_Prompt for s3_secret_key with type "password"
3. THE KSOPS_Adapter SHALL return Input_Prompt for s3_endpoint with type "string" and default value
4. THE KSOPS_Adapter SHALL return Input_Prompt for s3_region with type "string" and default value
5. THE KSOPS_Adapter SHALL return Input_Prompt for s3_bucket_name with type "string"
6. THE KSOPS_Adapter SHALL return Input_Prompt for github_app_id with type "string"
7. THE KSOPS_Adapter SHALL return Input_Prompt for github_app_installation_id with type "string"
8. THE KSOPS_Adapter SHALL return Input_Prompt for github_app_private_key with type "password"
9. THE KSOPS_Adapter SHALL return Input_Prompt for tenant_org_name with type "string"
10. THE KSOPS_Adapter SHALL return Input_Prompt for tenant_repo_name with type "string"

### Requirement 5: Pre-Work Script References

**User Story:** As a ZTC engine, I want pre-work script references executed before bootstrap, so that Age keypair and secrets are prepared.

#### Acceptance Criteria

1. THE KSOPS_Adapter SHALL return Script_Reference for 08b-generate-age-keys.sh in pre_work phase
2. THE KSOPS_Adapter SHALL return Script_Reference for setup-env-secrets.sh in pre_work phase
3. THE KSOPS_Adapter SHALL return Script_Reference for retrieve-age-key.sh in pre_work phase
4. THE KSOPS_Adapter SHALL return Script_Reference for inject-offline-key.sh in pre_work phase
5. THE KSOPS_Adapter SHALL return Script_Reference for create-age-backup.sh in pre_work phase
6. THE KSOPS_Adapter SHALL return Script_Reference for 08b-backup-age-to-s3.sh in pre_work phase
7. THE Script_References SHALL include S3 credentials in secret_env_vars where needed

### Requirement 6: Bootstrap Script References

**User Story:** As a ZTC engine, I want bootstrap script references with context data, so that scripts execute with correct parameters.

#### Acceptance Criteria

1. THE KSOPS_Adapter SHALL return Script_Reference for 00-inject-identities.sh in bootstrap phase
2. THE KSOPS_Adapter SHALL return Script_Reference for 03-bootstrap-storage.sh with S3 credentials in context_data
3. THE KSOPS_Adapter SHALL return Script_Reference for 08a-install-ksops.sh in bootstrap phase
4. THE KSOPS_Adapter SHALL return Script_Reference for 08c-inject-age-key.sh in bootstrap phase
5. THE KSOPS_Adapter SHALL return Script_Reference for 08d-create-age-backup.sh in bootstrap phase
6. THE KSOPS_Adapter SHALL return Script_Reference for apply-env-substitution.sh with tenant repo URLs in context_data
7. THE KSOPS_Adapter SHALL return Script_Reference for 08e-deploy-ksops-package.sh in bootstrap phase

### Requirement 7: Post-Work Script References

**User Story:** As a ZTC engine, I want post-work script references, so that KSOPS readiness is verified before proceeding.

#### Acceptance Criteria

1. THE KSOPS_Adapter SHALL return Script_Reference for 09c-wait-ksops-sidecar.sh in post_work phase
2. THE Script_Reference SHALL include timeout value in context_data

### Requirement 8: Validation Script References

**User Story:** As a ZTC engine, I want validation script references, so that KSOPS deployment can be verified.

#### Acceptance Criteria

1. THE KSOPS_Adapter SHALL return Script_Reference for 11-verify-ksops.sh in validation phase
2. THE KSOPS_Adapter SHALL return Script_Reference for validate-ksops-package.sh in validation phase
3. THE KSOPS_Adapter SHALL return Script_Reference for validate-secret-injection.sh in validation phase
4. THE KSOPS_Adapter SHALL return Script_Reference for validate-age-keys-and-storage.sh with S3 credentials in context_data
5. THE KSOPS_Adapter SHALL return Script_Reference for validate-sops-config.sh in validation phase
6. THE KSOPS_Adapter SHALL return Script_Reference for validate-sops-encryption.sh in validation phase
7. THE KSOPS_Adapter SHALL return Script_Reference for validate-age-key-decryption.sh in validation phase

### Requirement 9: Script Extraction and Embedding

**User Story:** As a ZTC engine, I want scripts embedded as package resources, so that they can be extracted to secure temp directories during execution.

#### Acceptance Criteria

1. THE KSOPS_Adapter SHALL embed all pre_work scripts in ztc.adapters.ksops.scripts.pre_work package
2. THE KSOPS_Adapter SHALL embed all bootstrap scripts in ztc.adapters.ksops.scripts.bootstrap package
3. THE KSOPS_Adapter SHALL embed all post_work scripts in ztc.adapters.ksops.scripts.post_work package
4. THE KSOPS_Adapter SHALL embed all validation scripts in ztc.adapters.ksops.scripts.validation package
5. THE KSOPS_Adapter SHALL embed all generator scripts in ztc.adapters.ksops.scripts.generators package
6. WHEN the ZTC_Engine extracts scripts, THE System SHALL preserve executable permissions
7. WHEN the ZTC_Engine extracts scripts, THE System SHALL inline helper functions from zerotouch-platform

### Requirement 10: Context File Generation

**User Story:** As a ZTC engine, I want context files generated for each script, so that parameters are passed securely without CLI arguments.

#### Acceptance Criteria

1. WHEN generating context files, THE System SHALL create JSON file with all context_data from Script_Reference
2. WHEN generating context files, THE System SHALL set ZTC_CONTEXT_FILE environment variable to file path
3. WHEN generating context files, THE System SHALL validate JSON is well-formed
4. WHEN generating context files, THE System SHALL include S3 credentials for scripts that require them
5. WHEN generating context files, THE System SHALL include GitHub App credentials for scripts that require them

### Requirement 11: Capability Data Provision

**User Story:** As a ZTC engine, I want the KSOPS adapter to provide secrets-management capability, so that dependent adapters can access Age key metadata.

#### Acceptance Criteria

1. WHEN rendering completes, THE KSOPS_Adapter SHALL provide secrets-management capability
2. THE secrets-management capability SHALL include Age public key
3. THE secrets-management capability SHALL include S3 bucket name
4. THE secrets-management capability SHALL include SOPS configuration path

### Requirement 12: Capability Dependency Resolution

**User Story:** As a ZTC engine, I want the KSOPS adapter to require kubernetes-api capability, so that it executes after cluster creation.

#### Acceptance Criteria

1. THE KSOPS_Adapter SHALL declare kubernetes-api as required capability
2. WHEN the ZTC_Engine resolves dependencies, THE System SHALL execute KSOPS adapter after adapters providing kubernetes-api
3. WHEN kubernetes-api capability is unavailable, THE ZTC_Engine SHALL fail with dependency error

### Requirement 13: Adapter Registry Integration

**User Story:** As a ZTC engine, I want the KSOPS adapter registered, so that it appears in ztc init selection menus.

#### Acceptance Criteria

1. THE Adapter_Registry SHALL discover KSOPS adapter from ztc.adapters.ksops package
2. THE Adapter_Registry SHALL load adapter.yaml metadata
3. THE Adapter_Registry SHALL validate adapter implements PlatformAdapter interface
4. WHEN running ztc init, THE System SHALL display KSOPS adapter in secrets_management selection group

### Requirement 14: Render Method Implementation

**User Story:** As a ZTC engine, I want the render method to generate manifests and capability data, so that the adapter integrates with the rendering pipeline.

#### Acceptance Criteria

1. THE render method SHALL accept ContextSnapshot parameter
2. THE render method SHALL access kubernetes-api capability from ContextSnapshot
3. THE render method SHALL return AdapterOutput with manifests dictionary
4. THE render method SHALL return AdapterOutput with capabilities dictionary containing secrets-management
5. THE render method SHALL return AdapterOutput with empty stages list

### Requirement 15: Script Enum Definition

**User Story:** As a developer, I want script paths defined as enums, so that typos are caught at class load time.

#### Acceptance Criteria

1. THE KSOPS_Adapter SHALL define KSOPSScripts enum with all script paths (pre_work, bootstrap, post_work, validation, generators)
2. THE KSOPSScripts enum SHALL include 28 total script paths (6 pre_work + 7 bootstrap + 1 post_work + 7 validation + 7 generators)
3. THE KSOPSScripts enum SHALL validate script files exist at class load time
4. WHEN referencing scripts, THE KSOPS_Adapter SHALL use enum values instead of string literals

### Requirement 16: Helper Function Inlining

**User Story:** As a developer, I want helper functions inlined into scripts, so that scripts are self-contained without external dependencies.

#### Acceptance Criteria

1. WHEN extracting scripts from zerotouch-platform, THE System SHALL inline s3-helpers.sh functions
2. WHEN extracting scripts, THE System SHALL inline env-helpers.sh functions
3. WHEN extracting scripts, THE System SHALL remove source statements for external helpers
4. WHEN extracting scripts, THE System SHALL preserve core business logic unchanged

### Requirement 17: Error Handling and Validation

**User Story:** As a platform operator, I want clear error messages, so that I can troubleshoot configuration issues.

#### Acceptance Criteria

1. WHEN configuration validation fails, THE System SHALL display which fields are invalid
2. WHEN required capabilities are missing, THE System SHALL display which capabilities are unavailable
3. WHEN script execution fails, THE System SHALL display script name and exit code
4. WHEN context file is missing, THE System SHALL display descriptive error message

### Requirement 18: Adapter Versioning

**User Story:** As a platform operator, I want adapter versions tracked, so that I can pin specific KSOPS versions.

#### Acceptance Criteria

1. THE Adapter_Metadata SHALL declare version field following semver format
2. THE Adapter_Metadata SHALL declare supported_versions list for SOPS/Age tool versions
3. WHEN rendering, THE System SHALL use default_version if not specified in configuration
