# ZTC - ZeroTouch Composition Engine

ZTC is a CLI tool for bare-metal Kubernetes cluster bootstrapping with a multi-adapter architecture. It provides progressive configuration collection, dependency resolution, and artifact generation for platform infrastructure.

## Features

- **Multi-Adapter Architecture**: Modular adapters for cloud providers (Hetzner), networking (Cilium), and OS (Talos)
- **Capability-Based Dependencies**: Automatic adapter ordering based on capability requirements
- **Progressive Configuration**: Interactive CLI wizard for platform setup
- **Lock File Safety**: Prevents drift between rendered artifacts and configuration
- **Atomic Rendering**: All-or-nothing artifact generation with rollback
- **Debug Mode**: Preserve workspace for troubleshooting failed renders
- **Eject Workflow**: Extract scripts and pipeline for manual debugging

## Installation

### From Source

```bash
# Clone repository
git clone https://github.com/your-org/zerotouch-engine.git
cd zerotouch-engine

# Install with Poetry
poetry install

# Run CLI
poetry run ztc --help
```

### Binary Distribution (Coming Soon)

```bash
# Download binary
curl -L https://github.com/your-org/zerotouch-engine/releases/latest/download/ztc -o ztc
chmod +x ztc

# Run
./ztc --help
```

## Quick Start

### 1. Initialize Platform Configuration

```bash
# Interactive wizard (coming soon)
ztc init

# Or create platform.yaml manually
cat > platform.yaml <<EOF
adapters:
  hetzner:
    version: v1.0.0
    api_token: your_hetzner_token
    server_ips:
      - 192.168.1.1
  cilium:
    version: v1.18.5
    bgp:
      enabled: false
  talos:
    version: v1.11.5
    factory_image_id: your_factory_image_id
    cluster_name: my-cluster
    cluster_endpoint: 192.168.1.1:6443
    nodes:
      - name: cp01
        ip: 192.168.1.1
        role: controlplane
EOF
```

### 2. Render Artifacts

```bash
# Generate manifests and configs
ztc render

# Artifacts written to platform/generated/
# Lock file created at platform/lock.json
```

### 3. Validate Artifacts

```bash
# Verify artifacts match lock file
ztc validate
```

### 4. Bootstrap Cluster (Coming Soon)

```bash
# Execute bootstrap pipeline
ztc bootstrap --env production
```

## CLI Commands

### `ztc init`

Initialize platform configuration via interactive prompts (coming soon).

**Options:**
- `--resume`: Resume from existing platform.yaml

### `ztc render`

Generate platform artifacts from platform.yaml.

**Options:**
- `--debug`: Preserve workspace on failure
- `--partial <adapter>`: Render specific adapters only

**Example:**
```bash
# Render all adapters
ztc render

# Render only Cilium adapter
ztc render --partial cilium

# Debug mode
ztc render --debug
```

### `ztc validate`

Validate generated artifacts against lock file.

**Example:**
```bash
ztc validate
```

### `ztc bootstrap`

Execute bootstrap pipeline (coming soon).

**Options:**
- `--env <environment>`: Target environment (default: production)
- `--skip-cache`: Ignore stage cache

### `ztc eject`

Eject scripts and pipeline for manual debugging.

**Options:**
- `--env <environment>`: Target environment (default: production)
- `--output <directory>`: Output directory (default: debug)

**Example:**
```bash
ztc eject --output debug-output
```

### `ztc vacuum`

Clean up stale temporary directories from crashed runs.

**Example:**
```bash
ztc vacuum
```

### `ztc version`

Display CLI version and embedded adapter versions.

**Example:**
```bash
ztc version
```

## Architecture

### Adapters

ZTC uses a capability-based adapter system:

- **Hetzner Adapter**: Provides `cloud-infrastructure` capability
- **Cilium Adapter**: Provides `cni` and `gateway-api` capabilities, requires `kubernetes-api`
- **Talos Adapter**: Provides `kubernetes-api` capability, requires `cloud-infrastructure` and `cni`

### Dependency Resolution

Adapters are executed in dependency order:
1. Hetzner (foundation) - provides server infrastructure
2. Cilium (networking) - provides CNI manifests
3. Talos (OS) - embeds CNI manifests and bootstraps Kubernetes

### Lock File

The lock file (`platform/lock.json`) tracks:
- Platform configuration hash
- Generated artifacts hash
- Adapter versions and metadata
- ZTC CLI version

This prevents drift between configuration and deployed artifacts.

## Development

### Running Tests

```bash
# All tests
poetry run pytest

# Unit tests only
poetry run pytest tests/unit/

# Integration tests only
poetry run pytest tests/integration/

# Specific test file
poetry run pytest tests/integration/test_render_pipeline.py -v
```

### Project Structure

```
zerotouch-engine/
├── ztc/                    # Main package
│   ├── adapters/          # Adapter implementations
│   │   ├── hetzner/
│   │   ├── cilium/
│   │   └── talos/
│   ├── commands/          # CLI command implementations
│   ├── engine/            # Core engine logic
│   ├── interfaces/        # Capability contracts
│   ├── registry/          # Adapter registry
│   ├── utils/             # Utilities
│   ├── workflows/         # Workflow implementations
│   ├── cli.py             # CLI entry point
│   └── exceptions.py      # Exception classes
├── tests/                 # Test suite
│   ├── unit/
│   └── integration/
└── pyproject.toml         # Poetry configuration
```

## Troubleshooting

### Render Fails with "No adapter outputs found"

Some adapters (like Hetzner) don't generate manifest files - they only provide capability data. Ensure you have at least one adapter that generates manifests (Cilium or Talos).

### Lock File Validation Fails

If you've modified `platform.yaml` after rendering, the lock file validation will fail. Re-render to update artifacts:

```bash
ztc render
```

### Missing Runtime Dependencies

Bootstrap requires external tools (jq, yq, kubectl, talosctl). Install missing tools:

```bash
# macOS
brew install jq yq kubectl

# Linux
apt-get install jq
snap install yq kubectl
```

### Debug Mode

Use `--debug` flag to preserve workspace on failure:

```bash
ztc render --debug
```

Workspace preserved at `.zerotouch-cache/workspace/`

## Contributing

See [ADAPTER_DEVELOPMENT.md](docs/ADAPTER_DEVELOPMENT.md) for adapter development guide.

## License

MIT License - see LICENSE file for details.