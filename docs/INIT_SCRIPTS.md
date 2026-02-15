# Init Scripts Lifecycle

## Overview

Init scripts execute during `ztc init` before cluster creation, enabling pre-cluster validation and external resource setup. This complements the existing bootstrap lifecycle which runs after cluster creation.

## Execution Order

1. **Init Phase** (`ztc init`) - Before cluster exists
   - Adapter configuration collection via interactive prompts
   - Init script execution per adapter in selection order
   - Platform.yaml generation

2. **Cluster Creation** - Infrastructure provisioning

3. **Bootstrap Phase** (`ztc bootstrap`) - After cluster exists
   - pre_work_scripts() - Pre-bootstrap setup
   - bootstrap_scripts() - Core deployment
   - post_work_scripts() - Post-deployment config
   - validation_scripts() - Verify success

## When to Use Init Scripts

**Use init scripts for:**
- External API validation (GitHub, cloud providers)
- External resource creation (S3 buckets, DNS records)
- Credential verification before cluster deployment
- Pre-cluster dependency checks

**Do NOT use init scripts for:**
- Kubernetes resource deployment (no cluster exists yet)
- Operations requiring kubectl or Kubernetes API
- In-cluster configuration or validation

## Script Organization Pattern

Init scripts follow the orchestrator pattern:
- Orchestrator script in `adapter/scripts/init/` reads context and coordinates
- Helper scripts co-located in same init directory
- All scripts use `$ZTC_CONTEXT_FILE` for data, environment variables for secrets
- No cross-phase dependencies (init scripts cannot call bootstrap scripts)

## Context Data vs Secrets

**Context Data** (via `$ZTC_CONTEXT_FILE`):
- Non-sensitive configuration (endpoints, regions, IDs)
- Passed as JSON file to avoid shell escaping issues
- Scripts read using jq: `jq -r '.field_name' "$ZTC_CONTEXT_FILE"`

**Secrets** (via environment variables):
- Sensitive credentials (API keys, private keys, passwords)
- Never included in context JSON file
- Accessed directly: `$SECRET_NAME`

## Adapter Selection Order

Adapters execute in this order, ensuring dependencies are met:
cloud_provider → git_provider → secrets_management → os → network_tool → gitops_platform → infrastructure_provisioner → DNS → TLS → gateway

Init scripts run immediately after each adapter's configuration is collected.

## Error Handling

- Init script failures halt execution immediately
- Error output displayed to user with script name and adapter context
- User must fix configuration issue and re-run `ztc init`
- Platform.yaml written incrementally for resume support
