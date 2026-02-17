#!/usr/bin/env bash
# Wait for KSOPS sidecar to be ready in ArgoCD repo server
#
# META_REQUIRE: timeout_seconds (context)

set -euo pipefail

# Validate context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

if [[ ! -f "$ZTC_CONTEXT_FILE" ]]; then
    echo "ERROR: Context file not found: $ZTC_CONTEXT_FILE" >&2
    exit 1
fi

# Read configuration from context
TIMEOUT=$(jq -r '.timeout_seconds // 300' "$ZTC_CONTEXT_FILE")
CHECK_INTERVAL=10
ARGOCD_NAMESPACE="argocd"

# Validate timeout
if [[ -z "$TIMEOUT" || "$TIMEOUT" == "null" ]]; then
    TIMEOUT=300
fi

echo "Waiting for KSOPS to be Ready"
echo "=============================="
echo ""
echo "⏳ Waiting for KSOPS to be ready (timeout: ${TIMEOUT}s)..."
echo "Namespace: $ARGOCD_NAMESPACE"
echo ""

ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    echo "=== Checking KSOPS sidecar status (${ELAPSED}s / ${TIMEOUT}s) ==="
    
    # Check if repo server deployment exists
    if ! kubectl get deployment argocd-repo-server -n "$ARGOCD_NAMESPACE" >/dev/null 2>&1; then
        echo "⏳ ArgoCD repo server deployment not found"
        sleep $CHECK_INTERVAL
        ELAPSED=$((ELAPSED + CHECK_INTERVAL))
        continue
    fi
    
    # Check if repo server pod exists
    REPO_POD=$(kubectl get pods -n "$ARGOCD_NAMESPACE" -l app.kubernetes.io/name=argocd-repo-server -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [[ -z "$REPO_POD" ]]; then
        echo "⏳ ArgoCD repo server pod not found"
        sleep $CHECK_INTERVAL
        ELAPSED=$((ELAPSED + CHECK_INTERVAL))
        continue
    fi
    
    echo "Found repo server pod: $REPO_POD"
    
    # Check if init container completed successfully
    INIT_STATUS=$(kubectl get pod "$REPO_POD" -n "$ARGOCD_NAMESPACE" -o jsonpath='{.status.initContainerStatuses[?(@.name=="install-ksops")].state.terminated.reason}' 2>/dev/null || echo "")
    
    if [[ "$INIT_STATUS" != "Completed" ]]; then
        echo "⏳ Init container install-ksops not completed yet (status: $INIT_STATUS)"
        sleep $CHECK_INTERVAL
        ELAPSED=$((ELAPSED + CHECK_INTERVAL))
        continue
    fi
    
    echo "✓ Init container install-ksops completed"
    
    # Check if main repo-server container is ready
    REPO_READY=$(kubectl get pod "$REPO_POD" -n "$ARGOCD_NAMESPACE" -o jsonpath='{.status.containerStatuses[?(@.name=="argocd-repo-server")].ready}' 2>/dev/null || echo "false")
    
    if [[ "$REPO_READY" != "true" ]]; then
        echo "⏳ Repo server container not ready yet"
        sleep $CHECK_INTERVAL
        ELAPSED=$((ELAPSED + CHECK_INTERVAL))
        continue
    fi
    
    echo "✓ Repo server container is ready"
    
    # Check if KSOPS tools are available
    echo "Checking KSOPS tools..."
    if kubectl exec "$REPO_POD" -n "$ARGOCD_NAMESPACE" -c argocd-repo-server -- test -f /.config/kustomize/plugin/viaduct.ai/v1/ksops/ksops 2>/dev/null; then
        echo "✓ KSOPS binary exists"
    else
        echo "⏳ KSOPS binary not found"
        sleep $CHECK_INTERVAL
        ELAPSED=$((ELAPSED + CHECK_INTERVAL))
        continue
    fi
    
    # Check if Age key file exists (optional check)
    echo "Checking Age key file..."
    if kubectl get secret sops-age -n "$ARGOCD_NAMESPACE" >/dev/null 2>&1; then
        echo "✓ Age key secret exists"
    else
        echo "⚠️  Age key secret not found (but sidecar is ready)"
    fi
    
    echo ""
    echo "✓ KSOPS is ready and operational!"
    echo ""
    exit 0
done

# Timeout reached
echo ""
echo "ERROR: Timeout waiting for KSOPS sidecar to be ready" >&2
echo ""

echo "Troubleshooting information:"
echo ""

# Show repo server pod status
echo "Repo Server Pod Status:"
kubectl get pods -n "$ARGOCD_NAMESPACE" -l app.kubernetes.io/name=argocd-repo-server 2>/dev/null || echo "Failed to get repo server pods"

echo ""
echo "Pod Description:"
kubectl describe pod -n "$ARGOCD_NAMESPACE" -l app.kubernetes.io/name=argocd-repo-server 2>/dev/null || echo "Failed to describe repo server pod"

echo ""
echo "Troubleshooting commands:"
echo "  kubectl logs -n $ARGOCD_NAMESPACE -l app.kubernetes.io/name=argocd-repo-server -c ksops"
echo "  kubectl logs -n $ARGOCD_NAMESPACE -l app.kubernetes.io/name=argocd-repo-server -c argocd-repo-server"
echo "  kubectl describe pod -n $ARGOCD_NAMESPACE -l app.kubernetes.io/name=argocd-repo-server"
echo ""

exit 1
