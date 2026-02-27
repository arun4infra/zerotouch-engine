#!/bin/bash
# Generate base Talos config using talosctl
set -euo pipefail

NODE_NAME="$1"
NODE_ROLE="$2"
NODE_IP="$3"
CLUSTER_NAME="$4"
CLUSTER_ENDPOINT="$5"
DISK_DEVICE="$6"
SECRETS_FILE="$7"
OUTPUT_DIR="$8"

echo "  Generating base config for $NODE_NAME ($NODE_ROLE)..."

# Create temp directory for generation
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Generate config using talosctl (CLUSTER_ENDPOINT already includes :6443)
talosctl gen config "$CLUSTER_NAME" "https://$CLUSTER_ENDPOINT" \
    --with-secrets "$SECRETS_FILE" \
    --output-types "$NODE_ROLE" \
    --output "$NODE_ROLE.yaml"

# Set basic machine config (match legacy template)
yq eval ".machine.network.nameservers = [\"8.8.8.8\", \"1.1.1.1\"]" -i "$NODE_ROLE.yaml"
yq eval ".machine.install.disk = \"$DISK_DEVICE\"" -i "$NODE_ROLE.yaml"

# Set cluster config to match legacy
yq eval ".cluster.proxy.disabled = true" -i "$NODE_ROLE.yaml"

# Move to output directory
mkdir -p "$OUTPUT_DIR"
mv "$NODE_ROLE.yaml" "$OUTPUT_DIR/config.yaml"

# Cleanup
cd - > /dev/null
rm -rf "$TEMP_DIR"

echo "  ✓ Base config generated"
