#!/bin/bash
# Embed Gateway API CRDs and Cilium manifests into control plane config
set -euo pipefail

CONFIG_FILE="$1"

echo "  Embedding Gateway API CRDs and Cilium manifests..."

# Check if Gateway API CRDs file exists (generated during render)
GATEWAY_API_MANIFEST="platform/generated/talos/gateway-api-crds.yaml"
if [ ! -f "$GATEWAY_API_MANIFEST" ]; then
    echo "ERROR: Gateway API CRDs not found at $GATEWAY_API_MANIFEST"
    echo "       This file should be generated during 'ztc render'"
    exit 1
fi

if [ ! -s "$GATEWAY_API_MANIFEST" ]; then
    echo "ERROR: Gateway API CRDs file is empty"
    exit 1
fi

echo "  ✓ Using Gateway API CRDs from render ($(wc -l < "$GATEWAY_API_MANIFEST") lines)"

# Check if CNI manifests file exists
CNI_MANIFEST="platform/generated/talos/cni-manifests.yaml"
if [ ! -f "$CNI_MANIFEST" ]; then
    echo "  Warning: CNI manifests not found, skipping Cilium embed"
    CNI_MANIFEST=""
fi

echo "  Embedding manifests into config..."

# Create temp file with Gateway API manifest entry
cat > /tmp/gateway-manifest-$$.yaml <<EOF
name: gateway-api-crds
contents: |
EOF
sed 's/^/  /' "$GATEWAY_API_MANIFEST" >> /tmp/gateway-manifest-$$.yaml

# Use yq to add Gateway API to inlineManifests array
yq eval ".cluster.inlineManifests[0] = load(\"/tmp/gateway-manifest-$$.yaml\")" -i "$CONFIG_FILE"

# Add Cilium if available
if [ -n "$CNI_MANIFEST" ]; then
    cat > /tmp/cilium-manifest-$$.yaml <<EOF
name: cilium-bootstrap
contents: |
EOF
    sed 's/^/  /' "$CNI_MANIFEST" >> /tmp/cilium-manifest-$$.yaml
    yq eval ".cluster.inlineManifests[1] = load(\"/tmp/cilium-manifest-$$.yaml\")" -i "$CONFIG_FILE"
    rm -f /tmp/cilium-manifest-$$.yaml
fi

# Cleanup
rm -f /tmp/gateway-manifest-$$.yaml

echo "  ✓ Network manifests embedded (Gateway API CRDs first, then Cilium)"
