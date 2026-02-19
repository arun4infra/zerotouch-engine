#!/bin/bash
# Embed Gateway API CRDs and Cilium CNI in Talos config
# Adapted from zerotouch-platform/scripts/bootstrap/install/02-embed-network-manifests.sh

set -euo pipefail

# Read context data from ZTC
if [ -z "${ZTC_CONTEXT_FILE:-}" ]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set"
    exit 1
fi

CLUSTER_NAME=$(jq -r '.cluster_name' "$ZTC_CONTEXT_FILE")
GATEWAY_API_VERSION="v1.4.1"

echo "Embedding network manifests for cluster: $CLUSTER_NAME"

# Paths relative to generated artifacts
CP_CONFIG="platform/generated/os/talos/nodes/cp01-main/config.yaml"
GATEWAY_API_MANIFEST="/tmp/gateway-api-crds.yaml"
CILIUM_MANIFEST="platform/generated/network/cilium/manifests.yaml"

# Download Gateway API CRDs
echo "Downloading Gateway API CRDs ${GATEWAY_API_VERSION}..."
if ! curl -sL "https://github.com/kubernetes-sigs/gateway-api/releases/download/${GATEWAY_API_VERSION}/standard-install.yaml" -o "$GATEWAY_API_MANIFEST"; then
    echo "ERROR: Failed to download Gateway API CRDs"
    exit 1
fi
echo "✓ Gateway API CRDs downloaded"

# Validate manifests exist
if [ ! -f "$GATEWAY_API_MANIFEST" ]; then
    echo "ERROR: Gateway API CRDs not found"
    exit 1
fi

if [ ! -f "$CILIUM_MANIFEST" ]; then
    echo "ERROR: Cilium manifest not found at: $CILIUM_MANIFEST"
    exit 1
fi

if [ ! -f "$CP_CONFIG" ]; then
    echo "ERROR: Control plane config not found at: $CP_CONFIG"
    exit 1
fi

# Remove existing inlineManifests if present
if grep -q "^[[:space:]]*inlineManifests:" "$CP_CONFIG"; then
    echo "Removing old inlineManifests section..."
    awk '
        /^[[:space:]]*inlineManifests:/ { 
            indent = match($0, /[^ ]/)
            skip=1
            next 
        }
        skip && /^[[:space:]]*[a-zA-Z]/ {
            current_indent = match($0, /[^ ]/)
            if (current_indent <= indent) {
                skip=0
            }
        }
        !skip { print }
    ' "$CP_CONFIG" > /tmp/cp-config-no-inline.yaml
    mv /tmp/cp-config-no-inline.yaml "$CP_CONFIG"
fi

# Find insertion point
LINE_NUM=$(grep -n "allowSchedulingOnControlPlanes:" "$CP_CONFIG" | cut -d: -f1)
if [ -z "$LINE_NUM" ]; then
    echo "ERROR: Could not find insertion point in control plane config"
    exit 1
fi

# Create inline manifests section
cat > /tmp/inline-manifest.yaml <<'EOF'
    inlineManifests:
        - name: gateway-api-crds
          contents: |
EOF

sed 's/^/            /' "$GATEWAY_API_MANIFEST" >> /tmp/inline-manifest.yaml

cat >> /tmp/inline-manifest.yaml <<'EOF'
        - name: cilium-bootstrap
          contents: |
EOF

sed 's/^/            /' "$CILIUM_MANIFEST" >> /tmp/inline-manifest.yaml

# Backup and insert
cp "$CP_CONFIG" "$CP_CONFIG.backup"

{
    head -n "$LINE_NUM" "$CP_CONFIG"
    cat /tmp/inline-manifest.yaml
    tail -n +$((LINE_NUM + 1)) "$CP_CONFIG"
} > /tmp/cp-config-new.yaml

mv /tmp/cp-config-new.yaml "$CP_CONFIG"
rm /tmp/inline-manifest.yaml "$GATEWAY_API_MANIFEST"

echo "✓ Gateway API CRDs and Cilium manifests embedded"
