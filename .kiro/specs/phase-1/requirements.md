# Requirements: ZTC Phase 1 - Multi-Adapter Foundation

## 1. Overview

Phase 1 establishes the ZeroTouch Composition (ZTC) engine with a multi-adapter architecture supporting Hetzner (cloud provider), Cilium (networking), and Talos (OS). The CLI provides progressive input collection via Typer + Rich, generating `platform.yaml` from user selections. Adapters embed scripts and templates, generating machine configs and pipeline stages for bare-metal Kubernetes bootstrap.

**Key Capabilities:**
- Interactive CLI wizard for adapter selection and configuration
- Resume capability (read existing platform.yaml, skip completed stages)
- Multi-adapter dependency resolution (phase + capability-based)
- Adapter lifecycle hooks (pre-work, post-work, validation)
- Version selection with defaults from embedded versions.yaml
- Script embedding (user never sees installation scripts)
- Jinja2 template-based manifest generation

## 2. User Stories

### 2.1 Platform Engineer - Progressive Input Collection

**As a** Platform Engineer  
**I want to** run `ztc init` and be guided through adapter selection via interactive prompts  
**So that** I don't need to manually write platform.yaml or understand all configuration options upfront

**As a** Platform Engineer  
**I want to** select adapters by category (cloud provider → network → OS) with version defaults  
**So that** I can quickly bootstrap a cluster with recommended configurations

**As a** Platform Engineer  
**I want to** resume interrupted `ztc init` sessions by reading existing platform.yaml  
**So that** I don't lose progress if the process is interrupted

### 2.2 Platform Engineer - Render Pipeline

**As a** Platform Engineer  
**I want to** run `ztc render` to generate machine configs and pipeline stages from platform.yaml  
**So that** I can review generated artifacts before committing to Git

**As a** Platform Engineer  
**I want to** validate generated artifacts against adapter schemas  
**So that** I catch configuration errors before bootstrap execution

### 2.3 Infrastructure Operator - Bootstrap Execution

**As an** Infrastructure Operator  
**I want to** execute `ztc bootstrap` with lock file validation  
**So that** I deploy exactly what was rendered (no drift)

**As an** Infrastructure Operator  
**I want to** see high-level progress (stage names, not script paths)  
**So that** I understand bootstrap status without implementation details

### 2.4 Adapter Developer - Lifecycle Hooks

**As an** Adapter Developer  
**I want to** implement pre-work, post-work, and validation lifecycle hooks  
**So that** my adapter integrates with the bootstrap pipeline pattern

**As an** Adapter Developer  
**I want to** declare supported versions and defaults in adapter metadata  
**So that** users can select from validated version combinations

## 3. Acceptance Criteria

### 3.1 CLI Commands - Interactive Input Collection

**Given** a platform engineer runs `ztc init`  
**When** no platform.yaml exists  
**Then** the system should:
- Display welcome message with Rich formatting
- Prompt for cloud provider selection (Hetzner, AWS, GCP)
- Prompt for provider-specific inputs (API token, server IPs)
- Prompt for network tool selection (Cilium, Calico, Flannel)
- Prompt for network tool version (show supported versions, highlight default)
- Prompt for OS selection (Talos, Flatcar, Ubuntu)
- Prompt for OS-specific inputs (cluster name, node definitions)
- Generate platform.yaml with all collected inputs
- Display summary table of selected adapters and versions

**Acceptance:**
- Typer prompts with type validation (IP format, token format)
- Rich progress bars for long operations
- Sensitive inputs (tokens, passwords) not echoed to terminal
- Generated platform.yaml is valid YAML with correct schema

---

**Given** a platform engineer runs `ztc init` with existing platform.yaml  
**When** platform.yaml has partial configuration  
**Then** the system should:
- Read existing platform.yaml
- Skip prompts for configured adapters
- Prompt only for missing adapter configurations
- Merge new inputs with existing configuration
- Preserve user comments and formatting where possible

**Acceptance:**
- Resume capability works for interrupted sessions
- Existing values displayed as defaults in prompts
- User can override existing values by providing new input
- platform.yaml updated incrementally (not regenerated from scratch)

---

**Given** a platform engineer selects Hetzner cloud provider  
**When** prompted for Hetzner-specific inputs  
**Then** the system should:
- Prompt for HCLOUD_TOKEN with validation (format check)
- Prompt for server IPs (comma-separated, IP format validation)
- Display warning about rescue mode prerequisite
- Store token encrypted or prompt for env var usage

**Acceptance:**
- Token validation checks format (not API validity at init time)
- IP validation accepts IPv4 format
- Clear error messages for invalid inputs
- Option to store token in env var instead of platform.yaml

---

**Given** a platform engineer selects Cilium network tool  
**When** prompted for Cilium configuration  
**Then** the system should:
- Display supported versions from embedded versions.yaml
- Highlight default version (v1.18.5 recommended)
- Prompt for BGP configuration (yes/no)
- If BGP enabled, prompt for ASN (integer validation)

**Acceptance:**
- Version list shows: v1.16.x, v1.17.x, v1.18.5 (recommended)
- Default version pre-selected (user can press Enter to accept)
- BGP ASN validates integer range
- Generated config includes selected version and BGP settings

---

**Given** a platform engineer selects Talos OS  
**When** prompted for Talos configuration  
**Then** the system should:
- Display supported versions (v1.10.x, v1.11.5 recommended)
- Prompt for cluster name (alphanumeric validation)
- Prompt for cluster endpoint (IP:port format)
- Prompt for node definitions (name, IP, role per node)
- Prompt for factory image ID (with explanation of what it is)

**Acceptance:**
- Cluster name validates alphanumeric + hyphens
- Cluster endpoint validates IP:port format
- Node definitions support multiple nodes (controlplane + workers)
- Factory image ID has help text explaining Talos image customization

### 3.2 Adapter Interface - Lifecycle Hooks

**Given** an adapter developer implements PlatformAdapter interface  
**When** the adapter is registered in the engine  
**Then** the adapter must provide:
- `adapter.yaml` metadata (name, version, phase, provides, requires, supported_versions, default_version)
- `schema.json` for user config validation
- `output-schema.json` for output data contract validation
- `get_required_inputs()` method returning list of interactive prompts
- `pre_work_scripts()` method returning installation/setup scripts
- `post_work_scripts()` method returning readiness wait scripts
- `validation_scripts()` method returning verification scripts
- `render(ctx: PlatformContext) -> AdapterOutput` method

**Acceptance:**
- Adapter without required methods is rejected at registration
- `get_required_inputs()` returns prompt definitions with validation rules
- Lifecycle hook methods return script references (not script content)
- Scripts referenced via internal URIs (e.g., `talos://install.sh`)

---

**Given** Talos adapter implements lifecycle hooks  
**When** engine calls lifecycle methods  
**Then** adapter should return:

**Pre-Work Scripts (Installation):**
- `talos://02-embed-network-manifests.sh` (embed Cilium CNI)
- `talos://03-install-talos.sh` (flash OS to bare-metal)
- `talos://04-bootstrap-talos.sh` (bootstrap etcd + kubeconfig)
- `talos://05-add-worker-nodes.sh` (add workers to cluster)

**Post-Work Scripts (Readiness):**
- None (Talos doesn't wait for itself)

**Validation Scripts:**
- `talos://validate-cluster.sh` (verify nodes joined)

**Acceptance:**
- Pre-work scripts execute in order during bootstrap
- Post-work scripts execute after pre-work completes
- Validation scripts always run (cache_key: null)
- Scripts resolved from adapter's embedded scripts directory

---

**Given** Cilium adapter implements lifecycle hooks  
**When** engine calls lifecycle methods  
**Then** adapter should return:

**Pre-Work Scripts:**
- None (Cilium embedded in Talos config, no separate installation)

**Post-Work Scripts (Readiness):**
- `cilium://wait-cilium.sh` (wait for CNI ready)
- `cilium://wait-gateway-api.sh` (wait for Gateway API CRDs)

**Validation Scripts:**
- `cilium://validate-cni.sh` (verify pod networking)

**Acceptance:**
- Post-work scripts wait for Cilium pods ready
- Validation scripts check CNI functionality
- Scripts have configurable timeouts (default 300s)

---

**Given** Hetzner adapter implements lifecycle hooks  
**When** engine calls lifecycle methods  
**Then** adapter should return:

**Pre-Work Scripts:**
- `hetzner://enable-rescue-mode.sh` (automate rescue mode activation)

**Post-Work Scripts:**
- None (Hetzner is infrastructure, no readiness wait)

**Validation Scripts:**
- `hetzner://validate-server-ids.sh` (verify providerID injection)

**Acceptance:**
- Pre-work script uses Hetzner API to enable rescue mode
- Script prompts for confirmation before destructive operations
- Validation script checks providerID format in node specs

### 3.3 Adapter Metadata - Version Selection

**Given** adapter metadata includes supported_versions and default_version  
**When** user selects adapter during `ztc init`  
**Then** CLI should:
- Display supported versions from adapter.yaml
- Highlight default version with "(recommended)" indicator
- Validate user selection against supported_versions list
- Store selected version in platform.yaml

**Acceptance:**
- Adapter.yaml includes `supported_versions: [v1.16.x, v1.17.x, v1.18.x]`
- Adapter.yaml includes `default_version: v1.18.5`
- CLI displays versions as selectable list (Typer choices)
- Invalid version selection rejected with error message

---

**Given** versions.yaml embedded in CLI binary  
**When** adapter needs version-specific artifacts  
**Then** adapter should:
- Query versions.yaml for artifact URLs/SHAs
- Use version-specific factory image IDs (Talos)
- Use version-specific operator image SHAs (Cilium)
- Validate artifact availability before render

**Acceptance:**
- versions.yaml is single source of truth for all adapter versions
- Adapter queries: `get_artifact('talos', 'v1.11.5', 'factory_image_id')`
- Missing artifacts fail render with clear error message
- versions.yaml embedded in CLI binary (not external file)

### 3.4 Dependency Resolution - Multi-Adapter

**Given** platform.yaml specifies Hetzner, Cilium, and Talos adapters  
**When** engine resolves dependencies  
**Then** the system should:
- Group adapters by phase (foundation, networking, platform, services)
- Build capability registry from `provides` declarations
- Resolve `requires` to concrete adapters via capability matching
- Perform topological sort within each phase
- Execute phases in order: foundation → networking → platform → services

**Acceptance:**
- Hetzner (foundation phase) executes first
- Cilium (networking phase) executes after Talos (foundation phase)
- Talos requires `cloud-infrastructure` capability (from Hetzner)
- Cilium requires `kubernetes-api` capability (from Talos)
- Circular dependencies detected and rejected with clear error

---

**Given** Talos adapter declares `requires: [capability: cloud-infrastructure]`  
**When** engine resolves dependencies  
**Then** the system should:
- Look up `cloud-infrastructure` in capability registry
- Find Hetzner adapter provides this capability
- Add Hetzner to dependency graph before Talos
- Fail if no adapter provides required capability

**Acceptance:**
- Capability registry maps: `cloud-infrastructure` → Hetzner adapter
- Missing capability error: "Adapter 'talos' requires capability 'cloud-infrastructure' but no adapter provides it"
- Dependency resolution uses Kahn's algorithm (topological sort)

### 3.5 Render Pipeline - Manifest Generation

**Given** valid platform.yaml with Hetzner, Cilium, Talos adapters  
**When** platform engineer runs `ztc render`  
**Then** the system should:
- Validate platform.yaml against adapter schemas
- Resolve adapter dependencies (phase + capability-based)
- Execute adapters in resolved order
- Call each adapter's `render(ctx)` method
- Write manifests to `platform/generated/{category}/{adapter}/`
- Generate pipeline YAML from adapter stage definitions
- Calculate artifacts hash and generate lock file
- Perform atomic swap of generated directory

**Acceptance:**
- Hetzner adapter generates: (no manifests, only exports server IDs)
- Cilium adapter generates: `platform/generated/network/cilium/manifests.yaml`
- Talos adapter generates: `platform/generated/os/talos/nodes/{name}/config.yaml`
- Pipeline YAML includes all adapter stages in execution order
- Lock file includes: platform_hash, ztc_version, artifacts_hash, adapters map
- Render is idempotent (no changes → no file modifications)

---

**Given** Talos adapter with node configuration  
**When** adapter's `render()` method executes  
**Then** adapter should:
- Load Jinja2 templates (controlplane.yaml.j2, worker.yaml.j2)
- Render templates with node-specific values (name, IP, role)
- Embed Cilium manifests from upstream adapter output
- Generate talosconfig for cluster access
- Return AdapterOutput with manifests dict

**Acceptance:**
- Generated machine configs validate with `talosctl validate --config <file>`
- Machine configs include Cilium CNI manifests (from Cilium adapter)
- Controlplane config has `cluster.controlPlane: true`
- Worker config has `cluster.controlPlane: false`
- Talosconfig includes cluster endpoint and credentials

---

**Given** Cilium adapter generates network manifests  
**When** Talos adapter requires CNI manifests  
**Then** engine should:
- Execute Cilium adapter first (networking phase)
- Store Cilium output in context
- Pass context to Talos adapter
- Talos adapter accesses: `ctx.get_data('cilium', 'manifests')`

**Acceptance:**
- Adapter execution order respects phase grouping
- Context provides `get_data(adapter_name, key)` method
- Talos adapter embeds Cilium manifests in machine configs
- Missing upstream data fails render with clear error

### 3.6 Bootstrap Execution - Stage Pipeline

**Given** rendered artifacts with valid lock file  
**When** infrastructure operator runs `ztc bootstrap --env production`  
**Then** the system should:
- Validate lock file environment matches `--env` flag
- Validate platform.yaml hash matches lock file
- Load generated pipeline YAML
- Execute stages sequentially via stage-executor pattern
- Resolve script URIs to adapter embedded scripts
- Track stage completion in cache file
- Display progress with Rich progress bars

**Acceptance:**
- Bootstrap fails fast if lock file environment ≠ `--env` flag
- Bootstrap fails fast if platform.yaml modified since render
- Stages execute in order defined by pipeline YAML
- Script URIs (e.g., `talos://install.sh`) resolved to adapter scripts
- Stage cache tracks completion: `.zerotouch-cache/bootstrap-stage-cache.json`
- User sees high-level progress: "Installing Talos OS..." (not script paths)

---

**Given** Talos adapter stage: `talos_install`  
**When** stage executes during bootstrap  
**Then** the system should:
- Resolve `talos://03-install-talos.sh` to adapter's embedded script
- Write script to temporary location (`/tmp/ztc-{uuid}/install.sh`)
- Execute script with args from stage definition
- Capture stdout/stderr for logging
- Mark stage complete in cache on success
- Clean up temporary script after execution

**Acceptance:**
- Script executes with correct arguments (SERVER_IP, ROOT_PASSWORD, etc.)
- Script output logged to `.zerotouch-cache/bootstrap.log`
- Stage cache updated: `{"stages": {"talos_install": "2026-02-12T10:30:00Z"}}`
- Temporary scripts cleaned from `/tmp/ztc-*` after execution
- Failed stage preserves cache (allows resume from failure point)

---

**Given** Cilium adapter post-work stage: `cilium_ready`  
**When** stage executes after Talos installation  
**Then** the system should:
- Execute `cilium://wait-cilium.sh` with timeout (300s default)
- Poll for Cilium pods ready status
- Retry with exponential backoff on failure
- Mark stage complete when Cilium operational

**Acceptance:**
- Wait script polls `kubectl get pods -n kube-system -l k8s-app=cilium`
- Timeout configurable via stage definition
- Retry logic: 5s, 10s, 20s, 40s intervals
- Stage fails after timeout with clear error message

---

**Given** validation stage with `cache_key: null`  
**When** bootstrap executes validation stages  
**Then** the system should:
- Execute validation script every time (ignore cache)
- Log validation results
- Continue on validation warnings (non-fatal)
- Fail bootstrap on validation errors (fatal)

**Acceptance:**
- Validation stages always run (even if previously completed)
- Warnings logged but don't stop bootstrap
- Errors stop bootstrap with actionable error message
- Validation results saved to `.zerotouch-cache/validation-report.json`

## 4. Non-Functional Requirements

### 4.1 Performance

- `ztc init` completes interactive prompts in <30 seconds (user input time excluded)
- `ztc render` completes in <10 seconds for 3 adapters (Hetzner, Cilium, Talos)
- Lock file generation adds <100ms overhead
- Atomic swap completes in <500ms for typical artifact size (~15 files)
- Bootstrap execution time depends on network/hardware (not engine overhead)

### 4.2 Reliability

- Render is atomic (all-or-nothing, no partial writes to `platform/generated/`)
- Lock file prevents drift between render and bootstrap
- Workspace isolation prevents accidental deletion of user files
- Stage cache enables resume from failure point
- Validation stages catch configuration errors before deployment

### 4.3 Usability

- CLI errors include actionable guidance (how to fix)
- `--help` text for all commands with examples
- `--debug` flag preserves artifacts for troubleshooting
- Rich formatting improves readability (colors, tables, progress bars)
- Sensitive inputs (tokens, passwords) not echoed to terminal

### 4.4 Security

- API tokens stored encrypted or prompted for env var usage
- Passwords never written to platform.yaml (runtime prompts only)
- Generated artifacts reviewed before Git commit
- Lock file prevents unauthorized modifications to generated artifacts
- Script execution isolated to temporary directories

### 4.5 Maintainability

- Adapter interface is stable (breaking changes require major version bump)
- Core engine has <10% code coverage requirement (focus on integration tests)
- Vertical slice (Hetzner + Cilium + Talos) serves as reference for future adapters
- Embedded scripts preserve existing bash logic (no Python rewrites)

## 5. Out of Scope (Phase 1)

- Additional adapters beyond Hetzner, Cilium, Talos (ArgoCD, KSOPS in Phase 2+)
- Parallel adapter rendering (sequential execution only)
- Kustomize overlay support (`platform/overlays/{env}/`)
- Capability interface validation (schema binding)
- Adapter update policies (Automatic/Manual)
- Garbage collection of old lock files
- Secret management (SecretReference, CSI integration)
- Team abstraction (RBAC, namespace management)
- Multi-controlplane HA clusters (single controlplane only)
- Custom Talos extensions (only factory image support)
- Cloud provider adapters beyond Hetzner (AWS, GCP in Phase 2+)
- Network tools beyond Cilium (Calico, Flannel in Phase 2+)

## 6. Success Metrics

- Platform engineer completes `ztc init` in <5 minutes (including input time)
- Platform engineer can render 3 adapters in <10 seconds
- Lock file prevents 100% of drift scenarios (manual edits detected)
- Atomic swap has 0% data loss rate (rollback on failure)
- Vertical slice (Hetzner + Cilium + Talos) validates end-to-end bootstrap on bare-metal
- CLI provides actionable error messages (user can fix without reading code)
- Bootstrap completes successfully from fresh Hetzner server to running Kubernetes cluster
- Generated machine configs validate with `talosctl validate`
- User never sees installation scripts (embedded in adapter)
- Resume capability works for interrupted workflows (90% of interrupted sessions resume successfully)

## 7. Dependencies & Tooling

### 7.1 Core Dependencies

- **Python 3.11+** (for engine implementation)
- **Poetry 1.8+** (dependency management and packaging)
- **Typer 0.12+** (CLI framework - modern, type-safe)
- **Rich 13.x** (terminal formatting, progress bars, tables)
- **PyYAML 6.x** (YAML parsing for platform.yaml and adapter metadata)
- **jsonschema 4.x** (schema validation for platform.yaml and adapter configs)
- **Pydantic 2.x** (data validation using Python type hints)
- **Jinja2 3.x** (template rendering for machine configs and manifests)
- **Git** (for lock file commit tracking)

### 7.2 External Tools (Runtime)

- **kubectl** (for validation and bootstrap execution)
- **kustomize** (for manifest validation)
- **talosctl** (for Talos machine config validation and cluster operations)
- **sshpass** (for password-based SSH to rescue mode)
- **jq** (for JSON parsing in bash scripts)
- **yq** (for YAML parsing in bash scripts)

### 7.3 Hetzner Integration

- **HCLOUD_TOKEN** (environment variable or platform.yaml)
- **hetzner-api.sh** helper (embedded in Hetzner adapter)
- **Hetzner API** (for server ID lookup, rescue mode automation)

**Hetzner API Operations:**
- `GET /servers` (list servers by IP)
- `POST /servers/{id}/actions/enable_rescue` (enable rescue mode)
- `POST /servers/{id}/actions/reboot` (reboot server)

**Required Inputs:**
- API token (format: 64-character hex string)
- Server IPs (IPv4 format validation)
- Rescue mode confirmation (destructive operation warning)

### 7.4 CLI Framework - Typer + Rich

**Typer Advantages:**
- Type hints = less boilerplate, better IDE support
- Built on Click (inherits stability) but modern API
- Auto-validation via Pydantic integration
- Used by FastAPI ecosystem (proven modern Python)

**Rich Advantages:**
- Beautiful terminal output (progress bars, tables, colors)
- Better UX for long operations (render, bootstrap)
- Syntax highlighting for YAML/JSON
- Spinner animations for waiting operations

**Poetry Advantages:**
- Modern dependency management (replaces pip + requirements.txt)
- Deterministic builds (poetry.lock)
- Easy packaging/distribution
- Standard in modern Python projects

**Example Typer + Rich Usage:**
```python
import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.progress import Progress
from typing import Optional

app = typer.Typer(help="ZeroTouch Composition Engine")
console = Console()

@app.command()
def init():
    """Initialize platform configuration via interactive prompts"""
    console.print("[bold blue]ZeroTouch Composition Engine[/bold blue]")
    console.print("Let's configure your platform...\n")
    
    # Cloud provider selection
    cloud_provider = Prompt.ask(
        "Select cloud provider",
        choices=["hetzner", "aws", "gcp"],
        default="hetzner"
    )
    
    # Version selection with default
    talos_version = Prompt.ask(
        "Select Talos version",
        choices=["v1.10.x", "v1.11.5"],
        default="v1.11.5"
    )
    
    # Confirmation prompt
    if Confirm.ask("Enable BGP mode?"):
        asn = Prompt.ask("Enter BGP ASN", default="64512")
    
    console.print("[green]✓[/green] Configuration complete")

@app.command()
def render():
    """Generate platform artifacts from platform.yaml"""
    with Progress() as progress:
        task = progress.add_task("Rendering adapters...", total=100)
        # ... render logic
        progress.update(task, advance=50)
```

### 7.5 Environment Variables Contract

**Bootstrap-Time Environment Variables:**

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `SERVER_IP` | Yes | Control plane server IP | `46.62.218.181` |
| `ROOT_PASSWORD` | Yes | Rescue mode SSH password | `rescue123` |
| `WORKER_NODES` | No | Comma-separated workers | `worker01:95.216.151.243` |
| `WORKER_PASSWORD` | No | Worker rescue password | `rescue456` |
| `ENV` | Yes | Environment name | `production` |
| `REPO_ROOT` | Yes | Repository root directory | `/path/to/repo` |
| `HCLOUD_TOKEN` | Yes | Hetzner API token | `abc123...` |

**Variable Sources:**
- Set by master bootstrap script before calling `ztc bootstrap`
- Read from `.env` file if present
- Prompted at runtime if missing (sensitive values only)

## 8. Adapter Architecture

### 8.1 Three-Adapter Phase 1 Scope

**Hetzner Adapter (Foundation Phase):**
- **Provides**: `cloud-infrastructure` capability
- **Requires**: None (foundation adapter)
- **Responsibilities**: Rescue mode automation, server ID lookup for providerID
- **Scripts**: `hetzner://enable-rescue-mode.sh`, `hetzner://api-helper.sh`
- **Config**: `HCLOUD_TOKEN`, server IPs
- **Output**: Server IDs, rescue mode credentials

**Cilium Adapter (Networking Phase):**
- **Provides**: `cni`, `gateway-api` capabilities
- **Requires**: `kubernetes-api` (from Talos)
- **Responsibilities**: Network manifest generation, CNI readiness validation
- **Scripts**: `cilium://wait-cilium.sh`, `cilium://wait-gateway-api.sh`
- **Config**: Version, BGP settings
- **Output**: Gateway API CRDs + Cilium CNI manifests

**Talos Adapter (Foundation Phase):**
- **Provides**: `kubernetes-api` capability
- **Requires**: `cloud-infrastructure` (Hetzner), `cni` manifests (Cilium)
- **Responsibilities**: Machine config generation, OS installation, cluster bootstrap
- **Scripts**: `talos://install.sh`, `talos://bootstrap.sh`, `talos://add-workers.sh`
- **Config**: Nodes, cluster_endpoint, factory_image_id
- **Output**: Machine configs, kubeconfig, cluster credentials

**Dependency Chain:**
```
Hetzner (foundation) → Talos (foundation) → Cilium (networking)
                           ↓
                    Embeds Cilium manifests
```

### 8.2 Adapter Input Requirements

**Hetzner Adapter Inputs:**
- `api_token` (string, 64-char hex, runtime prompt or env var)
- `server_ips` (list of IPv4 addresses)
- `rescue_mode_confirm` (boolean, confirmation prompt)

**Cilium Adapter Inputs:**
- `version` (string, from supported_versions list, default: v1.18.5)
- `bgp.enabled` (boolean, default: false)
- `bgp.asn` (integer, required if bgp.enabled=true)

**Talos Adapter Inputs:**
- `version` (string, from supported_versions list, default: v1.11.5)
- `factory_image_id` (string, 64-char hex)
- `cluster_name` (string, alphanumeric + hyphens)
- `cluster_endpoint` (string, IP:port format)
- `nodes` (list of {name, ip, role})
- `disk_device` (string, default: /dev/sda)

### 8.3 Adapter Lifecycle Hooks

**Interface Definition:**
```python
class PlatformAdapter:
    def get_required_inputs(self) -> List[InputPrompt]:
        """Return list of interactive prompts for user input collection"""
    
    def pre_work_scripts(self) -> List[ScriptReference]:
        """Return installation/setup scripts (cacheable stages)"""
    
    def post_work_scripts(self) -> List[ScriptReference]:
        """Return readiness wait scripts (cacheable stages)"""
    
    def validation_scripts(self) -> List[ScriptReference]:
        """Return verification scripts (always-run stages, cache_key: null)"""
    
    def render(self, ctx: PlatformContext) -> AdapterOutput:
        """Generate manifests, configs, and stage definitions"""
```

**Stage Type Mapping:**
- Pre-work scripts → Install stages (cache_key: stage_name)
- Post-work scripts → Wait stages (cache_key: stage_name)
- Validation scripts → Validation stages (cache_key: null, always run)

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Adapter interface too rigid | High - limits future adapters | Validate with 3-adapter vertical slice, iterate before Phase 2 |
| Lock file hash collisions | Medium - false positives | Use SHA256 (collision probability negligible) |
| Atomic swap fails on NFS | Medium - rollback may fail | Document filesystem requirements, test on common setups |
| CLI version skew | Low - users run old CLI | Lock file tracks CLI version, fail on downgrade |
| Jinja2 template injection | Medium - malicious templates | Validate template syntax, sanitize user inputs |
| Embedded script extraction | Low - users can't inspect scripts | Provide `ztc debug --show-scripts` command for transparency |
| Hetzner API rate limits | Medium - bootstrap failures | Implement exponential backoff, cache server IDs |
| Rescue mode timeout | Medium - servers don't boot | Configurable timeout, clear error messages |

## 10. Acceptance Testing Strategy

- **Unit Tests**: Adapter interface, lock file generation, hash calculation, Typer command parsing, Jinja2 template rendering
- **Integration Tests**: End-to-end `ztc init → render → validate → bootstrap` flow with 3 adapters
- **Vertical Slice Test**: Hetzner + Cilium + Talos adapters generate valid configs and deploy to bare-metal
- **Failure Tests**: Render failure rollback, lock file mismatch detection, missing capability errors
- **Performance Tests**: Render completes in <10 seconds for 3 adapters
- **CLI Tests**: Typer `CliRunner` tests for all commands, help text, error messages
- **Template Tests**: Jinja2 template rendering with various node configurations
- **Embedded Script Tests**: Verify adapter can retrieve embedded scripts via internal URIs
- **Machine Config Validation**: Generated configs validate with `talosctl validate --config <file>`
- **Stage Dependency Tests**: Verify stage execution order respects dependencies
- **Resume Tests**: Verify `ztc init` resumes from existing platform.yaml
- **Version Selection Tests**: Verify version prompts display defaults correctly
- **Lifecycle Hook Tests**: Verify pre-work, post-work, validation scripts execute in correct order
