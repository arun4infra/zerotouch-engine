#!/bin/bash
# Generate Cilium manifests for embedding in Talos
# This script generates the Cilium CNI manifests that will be embedded in Talos config

set -euo pipefail

echo "Generating Cilium manifests..."

# Cilium manifests are generated during render phase
# This is a placeholder - actual manifest generation happens in adapter.render()

echo "✓ Cilium manifests ready for embedding"
exit 0
