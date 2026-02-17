#!/bin/bash
# Verify nodes joined cluster
# Adapted from zerotouch-platform/scripts/bootstrap/validation/99-validate-cluster.sh

set -euo pipefail

# Read context data from ZTC
if [ -z "${ZTC_CONTEXT_FILE:-}" ]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set"
    exit 1
fi

EXPECTED_NODES=$(jq -r '.expected_nodes' "$ZTC_CONTEXT_FILE")

echo "Validating Talos cluster..."
echo "Expected nodes: $EXPECTED_NODES"

# Check dependencies
if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl not installed"
    exit 1
fi

# Validate cluster access
if ! kubectl get nodes &> /dev/null; then
    echo "ERROR: Cannot access cluster"
    exit 1
fi

# Count ready nodes
READY_NODES=$(kubectl get nodes --no-headers | grep -c " Ready " || true)

echo "Ready nodes: $READY_NODES / $EXPECTED_NODES"

if [ "$READY_NODES" -lt "$EXPECTED_NODES" ]; then
    echo "ERROR: Not all nodes are ready"
    kubectl get nodes
    exit 1
fi

echo "✓ All nodes are ready"

# Verify system pods
echo "Checking system pods..."
NOT_RUNNING=$(kubectl get pods -n kube-system --no-headers | grep -v "Running\|Completed" | wc -l || true)

if [ "$NOT_RUNNING" -gt 0 ]; then
    echo "WARNING: Some system pods are not running"
    kubectl get pods -n kube-system | grep -v "Running\|Completed"
else
    echo "✓ All system pods are running"
fi

echo "✓ Cluster validation complete"
