## Mapping from zerotouch-platform to ZTC

### Script Organization Mapping

**zerotouch-platform Structure:**
```
scripts/bootstrap/
├── helpers/
│   ├── hetzner-api.sh          # Shared Hetzner API functions
│   ├── bootstrap-config.sh     # Environment loading
│   └── fetch-tenant-config.sh  # Tenant config fetching
├── install/
│   ├── 02-embed-network-manifests.sh
│   ├── 03-install-talos.sh
│   ├── 04-bootstrap-talos.sh
│   └── 05-add-worker-nodes.sh
├── wait/
│   ├── 06-wait-cilium.sh
│   └── 06a-wait-gateway-api.sh
├── validation/
│   └── 99-validate-cluster.sh
└── 00-enable-rescue-mode.sh    # Pre-work for Talos
```

**ZTC Adapter Structure (Standardized):**
```
ztc/adapters/
├── hetzner/
│   ├── adapter.py              # HetznerAdapter class
│   ├── adapter.yaml            # Metadata
│   ├── config.py               # HetznerConfig Pydantic model
│   ├── templates/              # (empty - no manifests)
│   └── scripts/
│       ├── pre_work/           # (empty - no pre-work)
│       ├── bootstrap/          # (empty - no bootstrap scripts)
│       ├── post_work/          # (empty - no post-work)
│       └── validation/         # (empty - validation via Python API)
├── talos/
│   ├── adapter.py              # TalosAdapter class
│   ├── adapter.yaml            # Metadata
│   ├── config.py               # TalosConfig Pydantic model
│   ├── templates/
│   │   ├── controlplane.yaml.j2
│   │   └── worker.yaml.j2
│   └── scripts/
│       ├── pre_work/
│       │   └── enable-rescue-mode.sh      # Inlined Hetzner API
│       ├── bootstrap/
│       │   ├── embed-network-manifests.sh
│       │   ├── install-talos.sh
│       │   ├── bootstrap-talos.sh
│       │   └── add-worker-nodes.sh
│       ├── post_work/          # (empty - no post-work)
│       └── validation/
│           └── validate-cluster.sh
└── cilium/
    ├── adapter.py              # CiliumAdapter class
    ├── adapter.yaml            # Metadata
    ├── config.py               # CiliumConfig Pydantic model
    ├── templates/
    │   └── manifests.yaml.j2
    └── scripts/
        ├── pre_work/           # (empty - no pre-work)
        ├── bootstrap/
        │   ├── wait-cilium.sh
        │   └── wait-gateway-api.sh
        ├── post_work/          # (empty - no post-work)
        └── validation/
            └── validate-cni.sh
```

**Standard Adapter Directory Structure:**

All adapters MUST follow this structure:
```
adapter_name/
├── adapter.py              # Adapter implementation class
├── adapter.yaml            # Metadata and capability declarations
├── config.py               # Pydantic configuration model
├── templates/              # Jinja2 templates (can be empty)
└── scripts/
    ├── shared/             # Adapter-scoped shared helpers (optional)
    │   ├── s3-helpers.sh   # Example: S3 operations
    │   └── env-helpers.sh  # Example: Environment utilities
    ├── pre_work/           # Scripts before adapter bootstrap (can be empty)
    ├── bootstrap/          # Core adapter responsibility scripts (can be empty)
    ├── post_work/          # Scripts after adapter bootstrap (can be empty)
    └── validation/         # Validation scripts (can be empty)
```

**Benefits:**
- **Single Source of Truth**: Bug fixes in `shared/s3-helpers.sh` propagate to all scripts
- **Maintainability**: No copy-paste across 8+ scripts within adapter
- **Runtime Independence**: Extracted scripts remain self-contained
- **Adapter Isolation**: No cross-adapter helper dependencies

**Folder Purpose:**
- `pre_work/`: Infrastructure preparation before adapter can execute (e.g., rescue mode, disk prep)
- `bootstrap/`: Core adapter responsibility - main installation/deployment work (e.g., install OS, deploy manifests)
- `post_work/`: Additional configuration after adapter completes (e.g., wait for readiness, integrations, customizations)
- `validation/`: Verify adapter's work succeeded (e.g., connectivity tests, health checks)

### Adapter-to-Script Reference Table

| Adapter | Script Type | Original Script | ZTC Script | Context Data Keys |
|---------|-------------|-----------------|------------|-------------------|
| **Talos** | pre_work | `00-enable-rescue-mode.sh` | `pre_work/enable-rescue-mode.sh` | `server_ip`, `hetzner_api_token`, `confirm_destructive` |
| **Talos** | bootstrap | `install/02-embed-network-manifests.sh` | `bootstrap/embed-network-manifests.sh` | `cilium_manifests`, `gateway_api_crds` |
| **Talos** | bootstrap | `install/03-install-talos.sh` | `bootstrap/install-talos.sh` | `server_ip`, `user`, `password`, `disk_device`, `talos_version` |
| **Talos** | bootstrap | `install/04-bootstrap-talos.sh` | `bootstrap/bootstrap-talos.sh` | `controlplane_ip`, `talosconfig_path` |
| **Talos** | bootstrap | `install/05-add-worker-nodes.sh` | `bootstrap/add-worker-nodes.sh` | `worker_ips[]`, `talosconfig_path` |
| **Talos** | validation | `validation/99-validate-cluster.sh` | `validation/validate-cluster.sh` | `expected_node_count`, `kubeconfig_path` |
| **Cilium** | bootstrap | `wait/06-wait-cilium.sh` | `bootstrap/wait-cilium.sh` | `kubeconfig_path`, `timeout_seconds` |
| **Cilium** | bootstrap | `wait/06a-wait-gateway-api.sh` | `bootstrap/wait-gateway-api.sh` | `kubeconfig_path`, `timeout_seconds` |
| **Cilium** | validation | `validation/*` (CNI checks) | `validation/validate-cni.sh` | `kubeconfig_path`, `test_namespace` |

## Key Difference: Context Files vs CLI Arguments

### Original Platform Approach (CLI Arguments)

**Script Invocation:**
```bash
./scripts/bootstrap/install/03-install-talos.sh \
  --server-ip 46.62.218.181 \
  --user root \
  --password 'rescue123' \
  --disk /dev/sda \
  --talos-version v1.11.5 \
  --yes
```

**Script Argument Parsing:**
```bash
#!/bin/bash
# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --server-ip)
            SERVER_IP="$2"
            shift 2
            ;;
        --user)
            SSH_USER="$2"
            shift 2
            ;;
        --password)
            SSH_PASSWORD="$2"
            shift 2
            ;;
        # ... more args
    esac
done
```

### ZTC Approach (Context Files)

**Context File Generation (Python):**
```python
# ztc/core/executor.py
ScriptReference(
    package="ztc.adapters.talos.scripts.install",
    resource="install-talos.sh",
    context_data={
        "server_ip": "46.62.218.181",
        "user": "root",
        "password": "rescue123",
        "disk_device": "/dev/sda",
        "talos_version": "v1.11.5",
        "confirm_destructive": True
    }
)
```

**Context File (JSON):**
```json
{
  "server_ip": "46.62.218.181",
  "user": "root",
  "password": "rescue123",
  "disk_device": "/dev/sda",
  "talos_version": "v1.11.5",
  "confirm_destructive": true
}
```

**Script Context Reading (Bash):**
```bash
#!/usr/bin/env bash
set -euo pipefail

# Validate context file exists
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE environment variable not set" >&2
    exit 1
fi

if [[ ! -f "$ZTC_CONTEXT_FILE" ]]; then
    echo "ERROR: Context file not found: $ZTC_CONTEXT_FILE" >&2
    exit 1
fi

# Parse context with jq
SERVER_IP=$(jq -r '.server_ip' "$ZTC_CONTEXT_FILE")
SSH_USER=$(jq -r '.user' "$ZTC_CONTEXT_FILE")
SSH_PASSWORD=$(jq -r '.password' "$ZTC_CONTEXT_FILE")
DISK_DEVICE=$(jq -r '.disk_device // "/dev/sda"' "$ZTC_CONTEXT_FILE")
TALOS_VERSION=$(jq -r '.talos_version // "v1.11.5"' "$ZTC_CONTEXT_FILE")
CONFIRM=$(jq -r '.confirm_destructive // false' "$ZTC_CONTEXT_FILE")

# Validate required fields
if [[ -z "$SERVER_IP" || "$SERVER_IP" == "null" ]]; then
    echo "ERROR: server_ip is required in context" >&2
    exit 1
fi

# Core logic remains unchanged from original script
# ... (same Talos installation logic)
```

### Benefits of Context File Approach

1. **Type Safety**: JSON schema validation before script execution
2. **Auditability**: Context files can be logged and versioned
3. **Security**: Sensitive data (passwords, tokens) isolated in secure temp files
4. **Testability**: Easy to create test fixtures with mock context files
5. **Debugging**: Context files can be inspected during troubleshooting
6. **Consistency**: All scripts use same context reading pattern

## Core Logic Preservation

**Critical Principle**: The actual business logic of each script remains identical to the original zerotouch-platform implementation.

### What Changes:
- ❌ CLI argument parsing → ✅ JSON context reading
- ❌ Helper sourcing (`source helpers/hetzner-api.sh`) → ✅ Inlined functions
- ❌ Environment variable loading (`.env` files) → ✅ Context data
- ❌ Stage caching logic → ✅ Handled by stage-executor.sh
- ❌ Color output and user prompts → ✅ Handled by ZTC CLI

### What Stays the Same:
- ✅ Hetzner API calls (curl commands, endpoints, payloads)
- ✅ Talos installation commands (talosctl, disk flashing)
- ✅ Kubernetes validation logic (kubectl commands, readiness checks)
- ✅ Error handling and exit codes
- ✅ Retry logic and timeouts
- ✅ Core business logic flow

### Example: Hetzner API Function

**Original (helpers/hetzner-api.sh):**
```bash
hetzner_api() {
    local method="$1"
    local endpoint="$2"
    local data="$3"

    if [[ -n "$data" ]]; then
        curl -s -X "$method" \
            -H "Authorization: Bearer $HETZNER_API_TOKEN" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$HETZNER_API_URL$endpoint"
    else
        curl -s -X "$method" \
            -H "Authorization: Bearer $HETZNER_API_TOKEN" \
            "$HETZNER_API_URL$endpoint"
    fi
}
```

**ZTC (inlined in enable-rescue-mode.sh):**
```bash
# Read token from context instead of environment
HETZNER_API_TOKEN=$(jq -r '.hetzner_api_token' "$ZTC_CONTEXT_FILE")

# Same function, inlined
hetzner_api() {
    local method="$1"
    local endpoint="$2"
    local data="$3"

    if [[ -n "$data" ]]; then
        curl -s -X "$method" \
            -H "Authorization: Bearer $HETZNER_API_TOKEN" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "https://api.hetzner.cloud/v1$endpoint"
    else
        curl -s -X "$method" \
            -H "Authorization: Bearer $HETZNER_API_TOKEN" \
            "https://api.hetzner.cloud/v1$endpoint"
    fi
}

# Core logic unchanged
enable_rescue_mode() {
    local server_id=$(get_server_id_by_ip "$SERVER_IP")
    local response=$(hetzner_api "POST" "/servers/$server_id/actions/enable_rescue" '{"type":"linux64"}')
    echo "$response" | jq -r '.root_password'
}
```

## Capability System

### Capability Enum and Contracts

```python
from enum import Enum
from pydantic import BaseModel

class Capability(str, Enum):
    CLOUD_INFRASTRUCTURE = "cloud-infrastructure"
    KUBERNETES_API = "kubernetes-api"
    CNI_ARTIFACTS = "cni-artifacts"
    GATEWAY_API = "gateway-api"

class CloudInfrastructureCapability(BaseModel):
    provider: str
    region: str
    server_ids: List[str]

class KubernetesAPICapability(BaseModel):
    cluster_endpoint: str
    kubeconfig_path: str
    version: str

class CNIArtifactsCapability(BaseModel):
    manifests: str
    provider: str

CAPABILITY_CONTRACTS = {
    Capability.CLOUD_INFRASTRUCTURE: CloudInfrastructureCapability,
    Capability.KUBERNETES_API: KubernetesAPICapability,
    Capability.CNI_ARTIFACTS: CNIArtifactsCapability,
}
```

### Adapter Capability Declaration

**Hetzner Adapter:**
```python
class HetznerAdapter(PlatformAdapter):
    def provides_capabilities(self) -> List[Capability]:
        return [Capability.CLOUD_INFRASTRUCTURE]
    
    def requires_capabilities(self) -> List[Capability]:
        return []  # No dependencies
    
    async def render(self, context) -> AdapterOutput:
        # Query Hetzner API
        server_ids = await self._get_server_ids()
        
        return AdapterOutput(
            manifests={},  # No manifests
            capability_data={
                Capability.CLOUD_INFRASTRUCTURE: CloudInfrastructureCapability(
                    provider="hetzner",
                    region=self.config.region,
                    server_ids=server_ids
                )
            },
            pipeline_stages=[]  # No scripts
        )
```

**Talos Adapter:**
```python
class TalosAdapter(PlatformAdapter):
    def provides_capabilities(self) -> List[Capability]:
        return [Capability.KUBERNETES_API]
    
    def requires_capabilities(self) -> List[Capability]:
        return [
            Capability.CLOUD_INFRASTRUCTURE,  # Needs server IPs
            Capability.CNI_ARTIFACTS          # Needs Cilium manifests
        ]
    
    def pre_work_scripts(self) -> List[ScriptReference]:
        # Access cloud infrastructure capability for server IPs
        cloud_cap = self.context.get_capability_data(Capability.CLOUD_INFRASTRUCTURE)
        
        return [
            ScriptReference(
                package="ztc.adapters.talos.scripts.pre_work",
                resource="enable-rescue-mode.sh",
                context_data={
                    "server_ip": cloud_cap.server_ids[0],
                    "hetzner_api_token": self.config.hetzner_token
                }
            )
        ]
    
    def bootstrap_scripts(self) -> List[ScriptReference]:
        return [
            ScriptReference(
                package="ztc.adapters.talos.scripts.bootstrap",
                resource="install-talos.sh",
                context_data={
                    "server_ip": cloud_cap.server_ids[0],
                    "user": "root",
                    "password": self.config.rescue_password
                }
            )
        ]
```