#!/bin/bash
# Bootstrap Talos cluster
# Adapted from zerotouch-platform/scripts/bootstrap/install/04-bootstrap-talos.sh

set -euo pipefail

# Read context data from ZTC
if [ -z "${ZTC_CONTEXT_FILE:-}" ]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set"
    exit 1
fi

CLUSTER_ENDPOINT=$(jq -r '.cluster_endpoint' "$ZTC_CONTEXT_FILE")
CONTROLPLANE_IP=$(jq -r '.controlplane_ip' "$ZTC_CONTEXT_FILE")

echo "Bootstrapping Talos cluster..."
echo "Cluster Endpoint: $CLUSTER_ENDPOINT"
echo "Control Plane IP: $CONTROLPLANE_IP"

# Check dependencies
if ! command -v talosctl &> /dev/null; then
    echo "ERROR: talosctl not installed"
    exit 1
fi

# Paths to generated configs
TALOS_DIR="platform/generated/os/talos"
CP_CONFIG="$TALOS_DIR/nodes/cp01-main/config.yaml"
TALOSCONFIG="$TALOS_DIR/talosconfig"

if [ ! -f "$CP_CONFIG" ]; then
    echo "ERROR: Control plane config not found at: $CP_CONFIG"
    exit 1
fi

# Wait for Talos to boot
echo "Waiting 3 minutes for Talos to boot..."
sleep 180

# Get Hetzner server ID for providerID (if HCLOUD_TOKEN available)
PROVIDER_PATCH=""
if [ -n "${HCLOUD_TOKEN:-}" ]; then
    echo "Retrieving Hetzner server ID..."
    SERVER_ID=$(curl -s -H "Authorization: Bearer $HCLOUD_TOKEN" \
        "https://api.hetzner.cloud/v1/servers" | \
        jq -r ".servers[] | select(.public_net.ipv4.ip == \"$CONTROLPLANE_IP\") | .id")
    
    if [ -n "$SERVER_ID" ]; then
        PROVIDER_PATCH="[{\"op\": \"add\", \"path\": \"/machine/kubelet/extraArgs\", \"value\": {\"provider-id\": \"hcloud://$SERVER_ID\"}}]"
        echo "✓ Will inject providerID: hcloud://$SERVER_ID"
    fi
fi

# Apply configuration
echo "Applying Talos configuration..."
if ! talosctl apply-config --insecure \
    --nodes "$CONTROLPLANE_IP" \
    --endpoints "$CONTROLPLANE_IP" \
    --file "$CP_CONFIG" \
    --config-patch "$PROVIDER_PATCH"; then
    echo "Retrying in 10 seconds..."
    sleep 10
    talosctl apply-config --insecure \
        --nodes "$CONTROLPLANE_IP" \
        --endpoints "$CONTROLPLANE_IP" \
        --file "$CP_CONFIG" \
        --config-patch "$PROVIDER_PATCH"
fi

echo "Waiting 30 seconds for config to apply..."
sleep 30

# Bootstrap etcd
echo "Bootstrapping etcd cluster..."
talosctl bootstrap \
    --nodes "$CONTROLPLANE_IP" \
    --endpoints "$CONTROLPLANE_IP" \
    --talosconfig "$TALOSCONFIG"

echo "Waiting 60 seconds for API server..."
sleep 60

# Fetch kubeconfig
echo "Fetching kubeconfig..."
talosctl kubeconfig \
    --nodes "$CONTROLPLANE_IP" \
    --endpoints "$CONTROLPLANE_IP" \
    --talosconfig "$TALOSCONFIG" \
    --force

echo "✓ Talos cluster bootstrapped successfully"
