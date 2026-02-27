#!/bin/bash
# Embed Gateway API CRDs and Cilium Bootstrap Manifests into Talos Control Plane Config
# This adds static manifests to cluster.inlineManifests section
# Gateway API CRDs MUST be loaded BEFORE Cilium so Cilium detects Gateway API support
# Only applied to control plane - workers inherit CNI automatically
# Adapted from zerotouch-platform/scripts/bootstrap/install/02-embed-network-manifests.sh
#
# NOTE: As of v1.0, Gateway API CRDs are embedded at render time via controlplane.yaml.j2
# This script now validates that manifests are already present and skips re-embedding.

set -euo pipefail

# Read context data from ZTC
if [ -z "${ZTC_CONTEXT_FILE:-}" ]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set"
    exit 1
fi

CLUSTER_NAME=$(jq -r '.cluster_name' "$ZTC_CONTEXT_FILE")
CONTROL_PLANE_NODE=$(jq -r '.nodes[] | select(.role == "controlplane") | .name' "$ZTC_CONTEXT_FILE" | head -1)

echo "Checking network manifests for cluster: $CLUSTER_NAME"

if [ -z "$CONTROL_PLANE_NODE" ]; then
    echo "ERROR: No control plane node found in context"
    exit 1
fi

# Paths relative to generated artifacts
CP_CONFIG="platform/generated/talos/nodes/${CONTROL_PLANE_NODE}/config.yaml"

if [ ! -f "$CP_CONFIG" ]; then
    echo "ERROR: Control plane config not found at: $CP_CONFIG"
    exit 1
fi

# Check if inlineManifests already exist
if grep -q "^[[:space:]]*inlineManifests:" "$CP_CONFIG"; then
    echo "✓ inlineManifests section already exists in control plane config"
    
    # Validate Gateway API CRDs are present
    if grep -q "gateway-api-crds" "$CP_CONFIG"; then
        echo "✓ Gateway API CRDs manifest found"
    else
        echo "⚠️  Gateway API CRDs manifest not found in inlineManifests"
    fi
    
    # Validate Cilium manifests are present
    if grep -q "cilium" "$CP_CONFIG"; then
        echo "✓ Cilium CNI manifest found"
    else
        echo "⚠️  Cilium CNI manifest not found in inlineManifests"
    fi
    
    echo ""
    echo "Network manifests are already embedded (done at render time)"
    echo "Skipping re-embedding to preserve existing configuration"
    exit 0
fi

echo "⚠️  No inlineManifests found in control plane config"
echo "   This should have been added during 'ztc render'"
echo "   Please re-run 'ztc render' to generate proper configuration"
exit 1

# Read context data from ZTC
if [ -z "${ZTC_CONTEXT_FILE:-}" ]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set"
    exit 1
fi

CLUSTER_NAME=$(jq -r '.cluster_name' "$ZTC_CONTEXT_FILE")
CONTROL_PLANE_NODE=$(jq -r '.nodes[] | select(.role == "controlplane") | .name' "$ZTC_CONTEXT_FILE" | head -1)
GATEWAY_API_VERSION="v1.4.1"

echo "Embedding network manifests for cluster: $CLUSTER_NAME"

if [ -z "$CONTROL_PLANE_NODE" ]; then
    echo "ERROR: No control plane node found in context"
    exit 1
fi

# Paths relative to generated artifacts
CP_CONFIG="platform/generated/talos/nodes/${CONTROL_PLANE_NODE}/config.yaml"
GATEWAY_API_MANIFEST="/tmp/gateway-api-crds.yaml"
CILIUM_MANIFEST="platform/generated/talos/templates/cilium/02-configmaps.yaml"

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

echo "Embedding network manifests into control plane Talos config..."

# Remove existing inlineManifests if present
if grep -q "^[[:space:]]*inlineManifests:" "$CP_CONFIG"; then
    echo "⚠️  inlineManifests section already exists - removing old version"
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
    echo "✓ Old inlineManifests removed"
fi

# Find insertion point (add at end of cluster section)
LINE_NUM=$(grep -n "^cluster:" "$CP_CONFIG" | cut -d: -f1)
if [ -z "$LINE_NUM" ]; then
    echo "ERROR: Could not find cluster section in control plane config"
    exit 1
fi

# Find the end of the cluster section (next top-level key or end of file)
TOTAL_LINES=$(wc -l < "$CP_CONFIG")
INSERT_LINE=$TOTAL_LINES

# Create inline manifests section with Gateway API CRDs FIRST, then Cilium
cat > /tmp/inline-manifest.yaml <<'EOF'
  # Network manifests for bootstrap
  # Gateway API CRDs must load BEFORE Cilium for Gateway API support
  inlineManifests:
    - name: gateway-api-crds
      contents: |
EOF

# Add Gateway API CRDs (8 spaces indentation)
sed 's/^/        /' "$GATEWAY_API_MANIFEST" >> /tmp/inline-manifest.yaml

# Add Cilium manifest
cat >> /tmp/inline-manifest.yaml <<'EOF'
    - name: cilium-bootstrap
      contents: |
EOF

sed 's/^/        /' "$CILIUM_MANIFEST" >> /tmp/inline-manifest.yaml

# Backup and insert
cp "$CP_CONFIG" "$CP_CONFIG.backup-$(date +%Y%m%d-%H%M%S)"

# Append inline manifests at the end of the cluster section
cat "$CP_CONFIG" /tmp/inline-manifest.yaml > /tmp/cp-config-new.yaml

mv /tmp/cp-config-new.yaml "$CP_CONFIG"
rm /tmp/inline-manifest.yaml

echo "✓ Gateway API CRDs and Cilium manifests embedded in control plane config"
echo "  Gateway API CRDs will load first, then Cilium"
echo "  Cilium will detect Gateway API support on startup"
