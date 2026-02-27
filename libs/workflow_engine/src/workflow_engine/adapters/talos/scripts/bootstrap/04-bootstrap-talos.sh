#!/bin/bash
# Bootstrap Talos Cluster
# Adapted from zerotouch-platform/scripts/bootstrap/install/04-bootstrap-talos.sh
#
# This script:
# 1. Applies Talos configuration with provider ID
# 2. Bootstraps etcd cluster
# 3. Fetches kubeconfig
# 4. Verifies cluster is ready

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Kubectl retry function
kubectl_retry() {
    local max_attempts=20
    local timeout=15
    local attempt=1
    local exitCode=0

    while [ $attempt -le $max_attempts ]; do
        if timeout $timeout kubectl "$@"; then
            return 0
        fi

        exitCode=$?

        if [ $attempt -lt $max_attempts ]; then
            local delay=$((attempt * 2))
            echo -e "${YELLOW}⚠️  kubectl command failed (attempt $attempt/$max_attempts). Retrying in ${delay}s...${NC}" >&2
            sleep $delay
        fi

        attempt=$((attempt + 1))
    done

    echo -e "${RED}✗ kubectl command failed after $max_attempts attempts${NC}" >&2
    return $exitCode
}

# Read context data from ZTC
if [ -z "${ZTC_CONTEXT_FILE:-}" ]; then
    echo -e "${RED}ERROR: ZTC_CONTEXT_FILE not set${NC}"
    exit 1
fi

CLUSTER_ENDPOINT=$(jq -r '.cluster_endpoint' "$ZTC_CONTEXT_FILE")
CONTROLPLANE_IP=$(jq -r '.controlplane_ip' "$ZTC_CONTEXT_FILE")
CONTROL_PLANE_NODE=$(jq -r '.nodes[] | select(.role == "controlplane") | .name' "$ZTC_CONTEXT_FILE" | head -1)
ENV=$(jq -r '.env // "dev"' "$ZTC_CONTEXT_FILE")

if [ -z "$CONTROL_PLANE_NODE" ]; then
    echo -e "${RED}ERROR: No control plane node found in context${NC}"
    exit 1
fi

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Bootstrapping Talos Cluster ($ENV)                         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BLUE}Cluster Endpoint: $CLUSTER_ENDPOINT${NC}"
echo -e "${BLUE}Control Plane IP: $CONTROLPLANE_IP${NC}"

# Check dependencies
if ! command -v talosctl &> /dev/null; then
    echo -e "${RED}ERROR: talosctl not installed${NC}"
    exit 1
fi

# Paths to generated configs (use absolute paths)
REPO_ROOT="$(pwd)"
TALOS_DIR="$REPO_ROOT/platform/generated/talos"
CP_CONFIG="$TALOS_DIR/nodes/${CONTROL_PLANE_NODE}/config.yaml"
TALOSCONFIG="$TALOS_DIR/talosconfig"

if [ ! -f "$CP_CONFIG" ]; then
    echo -e "${RED}ERROR: Control plane config not found at: $CP_CONFIG${NC}"
    exit 1
fi

# 1. Prepare Configuration
echo -e "${BLUE}Preparing Configuration...${NC}"
echo -e "${GREEN}✓ Using Talos configuration: $CP_CONFIG${NC}"

# Wait for Talos to boot
echo -e "${BLUE}⏳ Waiting 2 minutes for Talos to boot...${NC}"
sleep 120

# 2. Apply Configuration
cd "$TALOS_DIR"

echo -e "${BLUE}Applying configuration to $CONTROLPLANE_IP...${NC}"

# Apply config (provider-id already included from generation)
if ! talosctl apply-config --insecure \
  --nodes "$CONTROLPLANE_IP" \
  --endpoints "$CONTROLPLANE_IP" \
  --file "$CP_CONFIG"; then
    echo -e "${RED}Failed to apply. Retrying in 10s...${NC}"
    sleep 10
    talosctl apply-config --insecure \
      --nodes "$CONTROLPLANE_IP" \
      --endpoints "$CONTROLPLANE_IP" \
      --file "$CP_CONFIG"
fi

echo -e "${BLUE}Waiting 30 seconds for config to apply...${NC}"
sleep 30

# 3. Bootstrap Etcd
echo -e "${BLUE}Bootstrapping etcd cluster...${NC}"
talosctl bootstrap \
  --nodes "$CONTROLPLANE_IP" \
  --endpoints "$CONTROLPLANE_IP" \
  --talosconfig talosconfig

echo -e "${BLUE}Waiting 60 seconds for API server...${NC}"
sleep 60

# 4. Fetch Kubeconfig
echo -e "${BLUE}Fetching kubeconfig...${NC}"
talosctl kubeconfig \
  --nodes "$CONTROLPLANE_IP" \
  --endpoints "$CONTROLPLANE_IP" \
  --talosconfig talosconfig \
  --force

echo ""
echo -e "${GREEN}✓ Talos cluster bootstrapped successfully${NC}"
echo ""
