#!/bin/bash
# Master script: Generate complete Talos configs with provider-id
# Orchestrates helper scripts to build final configs
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Read context from ZTC
if [ -z "${ZTC_CONTEXT_FILE:-}" ]; then
    echo -e "${RED}ERROR: ZTC_CONTEXT_FILE not set${NC}"
    exit 1
fi

CLUSTER_NAME=$(jq -r '.cluster_name' "$ZTC_CONTEXT_FILE")
CLUSTER_ENDPOINT=$(jq -r '.cluster_endpoint' "$ZTC_CONTEXT_FILE")
DISK_DEVICE=$(jq -r '.disk_device // "/dev/sda"' "$ZTC_CONTEXT_FILE")

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Generating Complete Talos Configs                          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check dependencies
for cmd in talosctl jq yq curl; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${RED}ERROR: $cmd not installed${NC}"
        exit 1
    fi
done

if [ -z "${HETZNER_API_TOKEN:-}" ]; then
    echo -e "${RED}ERROR: HETZNER_API_TOKEN not set${NC}"
    exit 1
fi

# Setup paths
REPO_ROOT="$(pwd)"
TALOS_DIR="$REPO_ROOT/platform/generated/talos"
CACHE_DIR="$REPO_ROOT/.zerotouch-cache"
SECRETS_FILE="$CACHE_DIR/talos-secrets.yaml"
HELPERS_DIR="$(dirname "$0")/helpers"

mkdir -p "$TALOS_DIR" "$CACHE_DIR"

# Generate secrets if not exists
if [ ! -f "$SECRETS_FILE" ]; then
    echo -e "${BLUE}Generating Talos secrets...${NC}"
    talosctl gen secrets -o "$SECRETS_FILE"
    echo -e "${GREEN}✓ Secrets generated${NC}"
else
    echo -e "${GREEN}✓ Using cached secrets${NC}"
fi

# Make helpers executable
chmod +x "$HELPERS_DIR"/*.sh

# Parse nodes from context
NODES=$(jq -c '.nodes[]' "$ZTC_CONTEXT_FILE")
NODE_COUNT=$(jq '.nodes | length' "$ZTC_CONTEXT_FILE")

echo -e "${BLUE}Processing nodes...${NC}"
echo ""

# Load environment and overlay config for allowSchedulingOnControlPlanes
ENV=$(jq -r '.env // "dev"' "$ZTC_CONTEXT_FILE")
OVERLAY_CONFIG="$REPO_ROOT/libs/workflow_engine/src/workflow_engine/templates/overlays/$ENV/configs.yaml"

# Determine if single-node cluster
if [ "$NODE_COUNT" -lt 2 ]; then
    ALLOW_SCHEDULING="true"
    echo -e "${YELLOW}Single-node cluster detected - enabling workload scheduling on control plane${NC}"
    echo ""
elif [ -f "$OVERLAY_CONFIG" ]; then
    ALLOW_SCHEDULING=$(yq eval '.talos.allow_scheduling_on_control_planes // false' "$OVERLAY_CONFIG")
else
    ALLOW_SCHEDULING="false"
fi

for node in $NODES; do
    NODE_NAME=$(echo "$node" | jq -r '.name')
    NODE_IP=$(echo "$node" | jq -r '.ip')
    NODE_ROLE=$(echo "$node" | jq -r '.role')
    NODE_DIR="$TALOS_DIR/nodes/$NODE_NAME"
    
    echo -e "${BLUE}Node: $NODE_NAME ($NODE_ROLE) @ $NODE_IP${NC}"
    
    # Step 1: Generate base config
    "$HELPERS_DIR/generate-base-config.sh" \
        "$NODE_NAME" "$NODE_ROLE" "$NODE_IP" \
        "$CLUSTER_NAME" "$CLUSTER_ENDPOINT" "$DISK_DEVICE" \
        "$SECRETS_FILE" "$NODE_DIR"
    
    # Step 2: Add provider-id
    "$HELPERS_DIR/add-provider-id.sh" \
        "$NODE_IP" "$NODE_DIR/config.yaml" "$HETZNER_API_TOKEN"
    
    # Step 3: Embed CNI manifests (control plane only)
    if [ "$NODE_ROLE" = "controlplane" ]; then
        "$HELPERS_DIR/embed-cni-manifests.sh" "$NODE_DIR/config.yaml"
        
        # Step 4: Set allowSchedulingOnControlPlanes if single-node
        if [ "$ALLOW_SCHEDULING" = "true" ]; then
            yq eval ".cluster.allowSchedulingOnControlPlanes = true" -i "$NODE_DIR/config.yaml"
            echo -e "${GREEN}✓ Enabled scheduling on control plane${NC}"
        fi
    fi
    
    echo -e "${GREEN}✓ Config complete for $NODE_NAME${NC}"
    echo ""
done

# Step 4: Generate talosconfig (after all configs are ready)
echo -e "${BLUE}Generating talosconfig...${NC}"
"$HELPERS_DIR/generate-talosconfig.sh" \
    "$CLUSTER_NAME" "$CLUSTER_ENDPOINT" "$SECRETS_FILE" "$TALOS_DIR"

echo ""
echo -e "${GREEN}✓ All Talos configs generated successfully${NC}"
echo -e "${GREEN}  Configs: $TALOS_DIR/nodes/*/config.yaml${NC}"
echo -e "${GREEN}  Talosconfig: $TALOS_DIR/talosconfig${NC}"
echo ""
