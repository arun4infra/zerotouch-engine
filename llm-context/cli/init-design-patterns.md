# Init Command Design Patterns

## Command Structure
- `ztc init <env>` - Environment arg (dev/staging/prod) loads corresponding .env file
- Writes `platform/platform.yaml` with version and adapters config
- Incremental writes after each adapter for crash recovery

## Environment Variables
- Loads `.env.<env>` file at startup for environment-specific defaults
- Falls back to prompts if env vars missing (BOT_GITHUB_USERNAME, BOT_GITHUB_TOKEN)
- GitHub App Private Key loaded from `.env.global` with user confirmation

## Adapter Selection
- Hardcoded order: cloud_provider → git_provider → secrets_management → os → network_tool → gitops_platform → infrastructure_provisioner → DNS → TLS → gateway
- Single-option groups auto-selected without prompt
- Multi-option groups show arrow-key selection even with defaults
- Only adapters with `selection_group` in SELECTION_ORDER are shown

## Init Script Execution
- After each adapter configuration is collected, init scripts execute immediately
- Scripts run in adapter selection order: cloud_provider → git_provider → secrets_management → os → network_tool → gitops_platform → infrastructure_provisioner → DNS → TLS → gateway
- Init scripts validate external APIs, create resources, verify credentials before cluster creation
- GitHub init script creates tenant repository if it doesn't exist
- Failures halt execution with clear error messages
- Platform.yaml written incrementally after each adapter for crash recovery

## Input Collection
- Fields with defaults auto-selected, skip prompt (except passwords)
- Empty inputs rejected unless default exists
- All inputs trimmed with `.strip()`
- Password fields never auto-selected even with defaults

## Validation
- IP addresses validated with regex for comma-separated lists
- URLs must start with http/https and have valid domain
- GitHub App IDs accept only digits
- RSA private keys validated for BEGIN/END markers, accept single-line or multi-line
- Cluster endpoints validated as IP:PORT format
- Git repo URLs must end with .git

## Special Handling
- Talos nodes: iterates over Hetzner server_ips, prompts name/role per IP
- KSOPS s3_region: auto-extracted from s3_endpoint URL
- Cilium bgp_asn: skipped if bgp_enabled is false
- GitHub App Private Key: loaded from .env.local with validation
- Boolean fields with defaults auto-selected

## Output Format
- YAML with 2-space indentation
- Version field for config bumping
- Adapters nested under top-level key
- Lists properly indented

## User Experience
- Sample values shown in prompts (e.g., kube-prod, cp01)
- Validation errors show expected format
- Auto-detected values displayed with "(auto-selected)" or "(auto-detected)"
- Required field errors: "This field is required"
- Invalid format errors show help text
