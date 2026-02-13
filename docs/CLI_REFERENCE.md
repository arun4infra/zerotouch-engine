# CLI Command Reference

Complete reference for all ZTC CLI commands.

## Global Options

All commands support these global options:

- `--help`: Show help message and exit
- `--version`: Show version and exit (use `ztc version` for detailed info)

## Commands

### `ztc init`

Initialize platform configuration via interactive prompts.

**Status**: Coming soon

**Usage:**
```bash
ztc init [OPTIONS]
```

**Options:**
- `--resume`: Resume from existing platform.yaml

**Description:**

Guides you through platform configuration with interactive prompts:
1. Select cloud provider (Hetzner, AWS, GCP)
2. Configure provider-specific settings
3. Select network tool (Cilium, Calico, Flannel)
4. Configure network settings
5. Select OS (Talos, Flatcar, Ubuntu)
6. Configure OS and cluster settings

Generates `platform.yaml` with all collected inputs.

**Examples:**
```bash
# Start new configuration
ztc init

# Resume interrupted session
ztc init --resume
```

---

### `ztc render`

Generate platform artifacts from platform.yaml.

**Usage:**
```bash
ztc render [OPTIONS]
```

**Options:**
- `--debug`: Preserve workspace on failure for troubleshooting
- `--partial <adapter>`: Render only specified adapters (can be used multiple times)

**Description:**

Executes the render pipeline:
1. Resolves adapter dependencies
2. Creates workspace
3. Renders each adapter with immutable context snapshots
4. Writes manifests to workspace
5. Generates pipeline YAML
6. Validates artifacts
7. Atomically swaps to `platform/generated/`
8. Generates lock file

**Output:**
- `platform/generated/`: Generated manifests and configs
- `platform/lock.json`: Lock file with artifact hashes
- `bootstrap/pipeline/production.yaml`: Bootstrap pipeline

**Examples:**
```bash
# Render all adapters
ztc render

# Render only Cilium adapter
ztc render --partial cilium

# Render multiple specific adapters
ztc render --partial hetzner --partial talos

# Debug mode (preserves workspace on failure)
ztc render --debug
```

**Exit Codes:**
- `0`: Success
- `1`: Render failed

---

### `ztc validate`

Validate generated artifacts against lock file.

**Usage:**
```bash
ztc validate
```

**Description:**

Validates that:
- `platform.yaml` hash matches lock file
- Generated artifacts hash matches lock file
- No drift between configuration and artifacts

Use this before bootstrap to ensure artifacts match configuration.

**Examples:**
```bash
ztc validate
```

**Exit Codes:**
- `0`: Validation passed
- `1`: Validation failed (drift detected)

**Common Failures:**
- **platform.yaml modified**: Re-run `ztc render` to update artifacts
- **Artifacts modified**: Re-run `ztc render` to regenerate artifacts
- **Lock file missing**: Run `ztc render` to create lock file

---

### `ztc bootstrap`

Execute bootstrap pipeline.

**Status**: Coming soon

**Usage:**
```bash
ztc bootstrap [OPTIONS]
```

**Options:**
- `--env <environment>`: Target environment (default: `production`)
- `--skip-cache`: Ignore stage cache and re-run all stages

**Description:**

Executes the bootstrap pipeline:
1. Validates lock file
2. Extracts scripts to secure temp directory
3. Writes context files for scripts
4. Executes stages sequentially
5. Tracks completion in cache
6. Cleans up temp directory

**Examples:**
```bash
# Bootstrap production environment
ztc bootstrap

# Bootstrap staging environment
ztc bootstrap --env staging

# Force re-run all stages
ztc bootstrap --skip-cache
```

**Exit Codes:**
- `0`: Bootstrap completed successfully
- `1`: Bootstrap failed

**Prerequisites:**
- `jq`: JSON processor
- `yq`: YAML processor
- `kubectl`: Kubernetes CLI
- `talosctl`: Talos CLI (if using Talos adapter)

---

### `ztc eject`

Eject scripts and pipeline for manual debugging (break-glass mode).

**Usage:**
```bash
ztc eject [OPTIONS]
```

**Options:**
- `--env <environment>`: Target environment (default: `production`)
- `--output <directory>`: Output directory (default: `debug`)

**Description:**

Extracts all embedded scripts, context files, and pipeline.yaml to a debug directory for manual inspection and execution.

**Use Cases:**
- Debugging failed bootstrap stages
- Manual intervention during cluster setup
- Understanding script execution flow
- Customizing scripts for edge cases

**Output Structure:**
```
debug/
├── scripts/
│   ├── hetzner/
│   ├── cilium/
│   └── talos/
├── context/
│   ├── script1.json
│   └── script2.json
├── pipeline.yaml
└── README.md
```

**Examples:**
```bash
# Eject to default debug directory
ztc eject

# Eject to custom directory
ztc eject --output my-debug

# Eject staging environment
ztc eject --env staging
```

**Exit Codes:**
- `0`: Eject completed successfully
- `1`: Eject failed

---

### `ztc vacuum`

Clean up stale temporary directories from crashed runs.

**Usage:**
```bash
ztc vacuum
```

**Description:**

Removes `ztc-secure-*` directories older than 60 minutes from `/tmp`. This handles cases where SIGKILL (signal 9) prevented normal cleanup.

Runs automatically on CLI startup (silent unless stale directories found).

**Examples:**
```bash
# Manual cleanup
ztc vacuum
```

**Exit Codes:**
- `0`: Cleanup completed

---

### `ztc version`

Display CLI version and embedded adapter versions.

**Usage:**
```bash
ztc version
```

**Description:**

Displays:
- CLI version
- Embedded adapter versions
- Adapter phases
- Capabilities provided by each adapter

**Example Output:**
```
ZTC Version Information

CLI Version: 0.1.0-dev

┏━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Adapter     ┃ Version ┃ Phase      ┃ Provides              ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ Cilium      │ 1.0.0   │ networking │ cni, gateway-api      │
│ Hetzner     │ 1.0.0   │ foundation │ cloud-infrastructure  │
│ Talos Linux │ 1.0.0   │ foundation │ kubernetes-api        │
└─────────────┴─────────┴────────────┴───────────────────────┘
```

**Examples:**
```bash
ztc version
```

**Exit Codes:**
- `0`: Success

---

## Environment Variables

### `ZTC_CONTEXT_FILE`

Path to JSON context file for scripts. Set automatically by ZTC during bootstrap.

**Example:**
```bash
export ZTC_CONTEXT_FILE=/tmp/ztc-context-abc123.json
```

### `HCLOUD_TOKEN`

Hetzner Cloud API token (alternative to storing in platform.yaml).

**Example:**
```bash
export HCLOUD_TOKEN=your_token_here
ztc render
```

---

## Configuration File

### `platform.yaml`

Main configuration file for ZTC.

**Location**: Repository root

**Structure:**
```yaml
adapters:
  adapter-name:
    version: v1.0.0
    # Adapter-specific configuration
```

**Example:**
```yaml
adapters:
  hetzner:
    version: v1.0.0
    api_token: ${HCLOUD_TOKEN}
    server_ips:
      - 192.168.1.1
      - 192.168.1.2
  
  cilium:
    version: v1.18.5
    bgp:
      enabled: false
  
  talos:
    version: v1.11.5
    factory_image_id: abc123
    cluster_name: my-cluster
    cluster_endpoint: 192.168.1.1:6443
    nodes:
      - name: cp01
        ip: 192.168.1.1
        role: controlplane
      - name: worker01
        ip: 192.168.1.2
        role: worker
```

---

## Lock File

### `platform/lock.json`

Generated by `ztc render`, tracks artifact state.

**Structure:**
```json
{
  "ztc_version": "0.1.0",
  "platform_hash": "abc123...",
  "artifacts_hash": "def456...",
  "generated_at": "2026-02-12T10:30:00Z",
  "adapters": {
    "hetzner": {
      "version": "v1.0.0",
      "config_hash": "ghi789..."
    }
  }
}
```

**Purpose:**
- Prevents drift between configuration and artifacts
- Validates artifacts before bootstrap
- Tracks adapter versions

---

## Exit Codes

All commands use standard exit codes:

- `0`: Success
- `1`: Error (with error message)

---

## Error Handling

ZTC provides actionable error messages with remediation hints:

**Example Error:**
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Error                                                                  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Adapter 'talos' requires capability 'cloud-infrastructure' but no     │
│ adapter provides it                                                    │
│                                                                        │
│ Help:                                                                  │
│ Add an adapter that provides 'cloud-infrastructure' capability to     │
│ platform.yaml                                                          │
│                                                                        │
│ Adapters that provide 'cloud-infrastructure':                         │
│   - hetzner                                                            │
│   - aws                                                                │
│                                                                        │
│ Run 'ztc init' to add one of these adapters to your configuration     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Workflow Examples

### Complete Workflow

```bash
# 1. Initialize configuration
ztc init

# 2. Render artifacts
ztc render

# 3. Validate artifacts
ztc validate

# 4. Bootstrap cluster
ztc bootstrap

# 5. Verify deployment
kubectl get nodes
```

### Debug Failed Render

```bash
# Render with debug mode
ztc render --debug

# Inspect workspace
ls -la .zerotouch-cache/workspace/

# Fix issue and re-render
ztc render
```

### Manual Bootstrap

```bash
# Eject scripts for manual execution
ztc eject --output manual-bootstrap

# Inspect scripts
cd manual-bootstrap
cat README.md

# Execute manually
./scripts/talos/install-talos.sh
```

---

## See Also

- [README.md](../README.md) - Installation and quick start
- [ADAPTER_DEVELOPMENT.md](ADAPTER_DEVELOPMENT.md) - Creating new adapters
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues and solutions
