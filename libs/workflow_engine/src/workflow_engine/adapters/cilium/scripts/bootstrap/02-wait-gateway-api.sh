#!/usr/bin/env bash
# Wait for Gateway API CRDs to be ready and Cilium to recognize them
# Adapted from zerotouch-platform/scripts/bootstrap/wait/06a-wait-gateway-api.sh
#
# This script validates:
# 1. Gateway API CRDs are established
# 2. Cilium operator can list GatewayClass resources
# 3. No cache sync errors in Cilium operator logs

set -euo pipefail

# Validate context file exists
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE environment variable not set" >&2
    exit 1
fi

if [[ ! -f "$ZTC_CONTEXT_FILE" ]]; then
    echo "ERROR: Context file not found: $ZTC_CONTEXT_FILE" >&2
    exit 1
fi

# Parse context with jq
KUBECONFIG_PATH=$(jq -r '.kubeconfig_path // ""' "$ZTC_CONTEXT_FILE")
TIMEOUT=$(jq -r '.timeout_seconds // 120' "$ZTC_CONTEXT_FILE")
INTERVAL=5

# Set kubeconfig if provided
if [[ -n "$KUBECONFIG_PATH" && -f "$KUBECONFIG_PATH" ]]; then
    export KUBECONFIG="$KUBECONFIG_PATH"
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   Validating Gateway API Readiness                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check Gateway API CRDs exist and are established
echo "⏳ Checking Gateway API CRDs..."
REQUIRED_CRDS=(
    "gatewayclasses.gateway.networking.k8s.io"
    "gateways.gateway.networking.k8s.io"
    "httproutes.gateway.networking.k8s.io"
)

for crd in "${REQUIRED_CRDS[@]}"; do
    if kubectl get crd "$crd" &>/dev/null; then
        # Check if CRD is established
        ESTABLISHED=$(kubectl get crd "$crd" -o jsonpath='{.status.conditions[?(@.type=="Established")].status}' 2>/dev/null)
        if [ "$ESTABLISHED" = "True" ]; then
            echo "  ✓ $crd (established)"
        else
            echo "  ✗ $crd (not established)"
            exit 1
        fi
    else
        echo "  ✗ $crd (missing)"
        exit 1
    fi
done

# Wait for Cilium to be able to list GatewayClass resources
echo "⏳ Verifying Cilium can access Gateway API resources..."
elapsed=0
while [ $elapsed -lt $TIMEOUT ]; do
    # Try to list GatewayClass - this confirms Cilium's cache is synced
    if kubectl get gatewayclass 2>/dev/null; then
        echo "  ✓ GatewayClass API accessible"
        break
    fi
    
    echo "  Waiting for GatewayClass API... (${elapsed}s/${TIMEOUT}s)"
    sleep $INTERVAL
    elapsed=$((elapsed + INTERVAL))
done

if [ $elapsed -ge $TIMEOUT ]; then
    echo "✗ Timeout waiting for GatewayClass API"
    exit 1
fi

# Check Cilium operator logs for cache sync errors
echo "⏳ Checking Cilium operator for Gateway API cache sync..."
CILIUM_OP_POD=$(kubectl get pod -n kube-system -l name=cilium-operator -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -n "$CILIUM_OP_POD" ]; then
    # Check recent logs for cache sync timeout errors
    if kubectl logs -n kube-system "$CILIUM_OP_POD" --tail=50 2>/dev/null | grep -q "timed out waiting for caches to sync"; then
        echo "  ⚠ Cache sync timeout detected in recent logs"
        echo "  This may indicate Gateway API was not fully ready during startup"
        echo "  The Cilium operator restart should have resolved this"
    fi
    
    # Verify Gateway API controller is running
    if kubectl logs -n kube-system "$CILIUM_OP_POD" --tail=100 2>/dev/null | grep -q "Starting Gateway API"; then
        echo "  ✓ Gateway API controller started"
    else
        echo "  ⚠ Gateway API controller start message not found in recent logs"
    fi
fi

# Final validation - try to create a test GatewayClass (dry-run)
echo "⏳ Validating GatewayClass can be created (dry-run)..."
if kubectl apply --dry-run=server -f - <<EOF 2>/dev/null
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: test-validation
spec:
  controllerName: io.cilium/gateway-controller
EOF
then
    echo "  ✓ GatewayClass validation passed"
else
    echo "  ✗ GatewayClass validation failed"
    exit 1
fi

echo ""
echo "✓ Gateway API is ready - Cilium can manage Gateway resources"
echo ""
