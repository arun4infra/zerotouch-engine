#!/bin/bash
# Add Hetzner provider-id to Talos config
set -euo pipefail

NODE_IP="$1"
CONFIG_FILE="$2"
HETZNER_API_TOKEN="$3"

echo "  Looking up Hetzner server ID for $NODE_IP..."

# Lookup server ID
SERVER_ID=$(curl -s -H "Authorization: Bearer $HETZNER_API_TOKEN" \
    "https://api.hetzner.cloud/v1/servers" | \
    jq -r ".servers[] | select(.public_net.ipv4.ip == \"$NODE_IP\") | .id")

if [ -z "$SERVER_ID" ]; then
    echo "ERROR: Could not find server ID for IP $NODE_IP"
    exit 1
fi

echo "  ✓ Found server ID: $SERVER_ID"

# Add provider-id to config
yq eval ".machine.kubelet.extraArgs.\"provider-id\" = \"hcloud://$SERVER_ID\"" -i "$CONFIG_FILE"

echo "  ✓ Provider-id added: hcloud://$SERVER_ID"
