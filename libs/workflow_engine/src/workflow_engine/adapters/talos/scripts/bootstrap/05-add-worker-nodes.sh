#!/bin/bash
# Add worker nodes to cluster
# Adapted from zerotouch-platform/scripts/bootstrap/install/05-add-worker-nodes.sh

set -euo pipefail

# Read context data from ZTC
if [ -z "${ZTC_CONTEXT_FILE:-}" ]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set"
    exit 1
fi

WORKER_NODES=$(jq -c '.nodes[] | select(.role == "worker")' "$ZTC_CONTEXT_FILE")

# Check if any worker nodes exist
if [ -z "$WORKER_NODES" ]; then
    echo "No worker nodes defined in platform.yaml"
    echo "✓ Worker nodes stage skipped (no workers configured)"
    exit 0
fi

echo "Found worker nodes to process"
echo ""

# Check dependencies
if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl not installed"
    exit 1
fi

if ! command -v talosctl &> /dev/null; then
    echo "ERROR: talosctl not installed"
    exit 1
fi

# Validate cluster access
echo "Validating cluster access..."
if ! kubectl get nodes &> /dev/null; then
    echo "ERROR: Cannot access cluster. Is kubeconfig configured?"
    exit 1
fi
echo "✓ Cluster is accessible"

# Paths to generated configs
TALOS_DIR="platform/generated/os/talos"
TALOSCONFIG="$TALOS_DIR/talosconfig"

# Process each worker node
echo "$WORKER_NODES" | while IFS= read -r worker; do
    WORKER_NAME=$(echo "$worker" | jq -r '.name')
    WORKER_IP=$(echo "$worker" | jq -r '.ip')
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Adding worker: $WORKER_NAME ($WORKER_IP)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    WORKER_CONFIG="$TALOS_DIR/nodes/$WORKER_NAME/config.yaml"
    
    if [ ! -f "$WORKER_CONFIG" ]; then
        echo "ERROR: Worker config not found at: $WORKER_CONFIG"
        echo "Worker configs should be generated during talos_config stage"
        exit 1
    fi
    
    # Apply worker configuration (provider-id already embedded in config)
    echo "Applying worker configuration..."
    if ! talosctl apply-config --insecure \
        --nodes "$WORKER_IP" \
        --endpoints "$WORKER_IP" \
        --file "$WORKER_CONFIG"; then
        echo "Retrying in 30 seconds..."
        sleep 30
        talosctl apply-config --insecure \
            --nodes "$WORKER_IP" \
            --endpoints "$WORKER_IP" \
            --file "$WORKER_CONFIG"
    fi
    
    echo "Waiting 120 seconds for node to join..."
    sleep 120
    
    # Label worker node
    echo "Labeling worker node..."
    NODE_NAME_IN_CLUSTER=$(kubectl get nodes -o wide | grep "$WORKER_IP" | awk '{print $1}')
    if [ -n "$NODE_NAME_IN_CLUSTER" ]; then
        kubectl label node "$NODE_NAME_IN_CLUSTER" node-role.kubernetes.io/worker=worker --overwrite || true
        echo "✓ Node $NODE_NAME_IN_CLUSTER labeled"
    fi
    
    echo "✓ Worker $WORKER_NAME added successfully"
done

echo ""
echo "✓ All worker nodes added successfully"
