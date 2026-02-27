#!/bin/bash
# Generate talosconfig from secrets
set -euo pipefail

CLUSTER_NAME="$1"
CLUSTER_ENDPOINT="$2"
SECRETS_FILE="$3"
OUTPUT_DIR="$4"

echo "  Generating talosconfig..."

# Create temp directory for generation
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Generate config using talosctl (CLUSTER_ENDPOINT already includes :6443)
talosctl gen config "$CLUSTER_NAME" "https://$CLUSTER_ENDPOINT" \
    --with-secrets "$SECRETS_FILE" \
    --output-types talosconfig \
    --output "talosconfig"

# Move to output directory
mv talosconfig "$OUTPUT_DIR/talosconfig"

# Cleanup
cd - > /dev/null
rm -rf "$TEMP_DIR"

echo "  ✓ Talosconfig generated"
