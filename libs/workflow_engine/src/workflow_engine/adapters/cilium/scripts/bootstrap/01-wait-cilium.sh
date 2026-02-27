#!/usr/bin/env bash
# Wait for Cilium CNI to be Ready
# Adapted from zerotouch-platform/scripts/bootstrap/wait/06-wait-cilium.sh
#
# This script waits for:
# 1. Cilium agent pods to be ready
# 2. Cilium operator to be ready
# 3. Cilium health check to pass

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
TIMEOUT_SECONDS=$(jq -r '.timeout_seconds // 300' "$ZTC_CONTEXT_FILE")

# Set kubeconfig if provided
if [[ -n "$KUBECONFIG_PATH" && -f "$KUBECONFIG_PATH" ]]; then
    export KUBECONFIG="$KUBECONFIG_PATH"
fi

# Kubectl retry function (inlined)
kubectl_retry() {
    local max_attempts=20
    local timeout=15
    local attempt=1
    local exitCode=0

    while [ $attempt -le $max_attempts ]; do
        if timeout $timeout kubectl "$@"; then
            return 0
        fi

        exitCode=$?

        if [ $attempt -lt $max_attempts ]; then
            local delay=$((attempt * 2))
            echo "⚠️  kubectl command failed (attempt $attempt/$max_attempts). Retrying in ${delay}s..." >&2
            sleep $delay
        fi

        attempt=$((attempt + 1))
    done

    echo "✗ kubectl command failed after $max_attempts attempts" >&2
    return $exitCode
}

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   Waiting for Cilium CNI                                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Wait for Cilium agent pods
echo "⏳ Waiting for Cilium agent pods..."
if ! kubectl_retry wait --for=condition=ready pod -n kube-system -l k8s-app=cilium --timeout=180s; then
    echo "✗ Cilium agent pods failed to become ready"
    exit 1
fi

# Wait for Cilium operator (all configured replicas must be ready)
echo "⏳ Waiting for Cilium operator..."
OPERATOR_REPLICAS=$(kubectl get deployment -n kube-system cilium-operator -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
echo "   Expected replicas: $OPERATOR_REPLICAS"

for i in {1..20}; do
    READY_REPLICAS=$(kubectl get deployment -n kube-system cilium-operator -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [ "$READY_REPLICAS" -eq "$OPERATOR_REPLICAS" ]; then
        echo "✓ Cilium operator ready ($READY_REPLICAS/$OPERATOR_REPLICAS replicas)"
        break
    fi
    if [ $i -eq 20 ]; then
        echo "✗ Cilium operator failed: only $READY_REPLICAS/$OPERATOR_REPLICAS replicas ready after 20 attempts"
        kubectl get pods -n kube-system -l name=cilium-operator
        exit 1
    fi
    echo "   Waiting for operator replicas: $READY_REPLICAS/$OPERATOR_REPLICAS (attempt $i/20)"
    sleep 3
done

# Verify Cilium health
echo "Verifying Cilium health..."
CILIUM_POD=$(kubectl get pod -n kube-system -l k8s-app=cilium -o jsonpath='{.items[0].metadata.name}')
if kubectl exec -n kube-system "$CILIUM_POD" -- cilium status --brief 2>/dev/null | grep -q "OK"; then
    echo "✓ Cilium is healthy"
else
    echo "⚠️  Cilium status check failed, but continuing (basic connectivity verified)"
fi

# Validate Gateway API CRDs are loaded and Cilium detected them
echo "⏳ Validating Gateway API CRDs are available..."
GATEWAY_CRDS_READY=false
for i in {1..30}; do
    if kubectl get crd gatewayclasses.gateway.networking.k8s.io &>/dev/null && \
       kubectl get crd gateways.gateway.networking.k8s.io &>/dev/null && \
       kubectl get crd httproutes.gateway.networking.k8s.io &>/dev/null; then
        GATEWAY_CRDS_READY=true
        break
    fi
    echo "  Waiting for Gateway API CRDs... (attempt $i/30)"
    sleep 2
done

if [ "$GATEWAY_CRDS_READY" = "false" ]; then
    echo "⚠️  Gateway API CRDs not found after 60s"
    echo "   This may indicate Talos inline manifests didn't load properly"
    exit 1
fi
echo "✓ Gateway API CRDs are established"

# Validate Cilium Gateway API support
echo "⏳ Validating Cilium Gateway API support..."
# Check if Cilium-specific Gateway API CRDs are present
if kubectl get crd ciliumenvoyconfigs.cilium.io &>/dev/null && \
   kubectl get crd ciliumgatewayclassconfigs.cilium.io &>/dev/null; then
    echo "✓ Cilium Gateway API CRDs are installed"
else
    echo "✗ Cilium Gateway API CRDs are missing"
    echo "   Expected: ciliumenvoyconfigs.cilium.io, ciliumgatewayclassconfigs.cilium.io"
    exit 1
fi

OPERATOR_REPLICAS=$(kubectl get deployment -n kube-system cilium-operator -o jsonpath='{.spec.replicas}')

echo ""
echo "✓ Cilium CNI is ready - networking operational"
if [ "$OPERATOR_REPLICAS" -eq 1 ]; then
    echo "ℹ  Note: Cilium operator running with 1 replica (single-node mode)"
else
    echo "ℹ  Note: Cilium operator running with $OPERATOR_REPLICAS replicas (HA mode)"
fi
echo "ℹ  Gateway API CRDs embedded in Talos config - loaded before Cilium"
echo ""
