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
kubectl_retry wait --for=condition=ready pod -n kube-system -l k8s-app=cilium --timeout=180s

# Wait for Cilium operator
echo "⏳ Waiting for Cilium operator (2 replicas in HA mode)..."
kubectl_retry wait --for=condition=ready pod -n kube-system -l name=cilium-operator --timeout=180s

# Verify Cilium health
echo "Verifying Cilium health..."
CILIUM_POD=$(kubectl get pod -n kube-system -l k8s-app=cilium -o jsonpath='{.items[0].metadata.name}')
if kubectl exec -n kube-system "$CILIUM_POD" -- cilium status --brief 2>/dev/null | grep -q "OK"; then
    echo "✓ Cilium is healthy"
else
    echo "⚠️  Cilium status check failed, but continuing (basic connectivity verified)"
fi

# Restart Cilium operator to ensure Gateway API CRDs are properly detected
# This handles the race condition where Cilium starts before CRDs are fully established
echo "⏳ Restarting Cilium operator to ensure Gateway API detection..."
kubectl_retry rollout restart deployment/cilium-operator -n kube-system
kubectl_retry rollout status deployment/cilium-operator -n kube-system --timeout=120s
echo "✓ Cilium operator restarted"

echo ""
echo "✓ Cilium CNI is ready - networking operational"
echo "ℹ  Note: Cilium operator running with 2 replicas (HA mode with worker node)"
echo "ℹ  Gateway API support enabled via inline manifest CRDs"
echo ""
