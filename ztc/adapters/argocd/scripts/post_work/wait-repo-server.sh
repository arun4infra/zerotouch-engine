#!/usr/bin/env bash
set -euo pipefail

# Wait for ArgoCD Repo Server to be Responsive
# Tests connectivity to repo server ports and validates API functionality

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
NAMESPACE=$(jq -r '.namespace' "$ZTC_CONTEXT_FILE")
TIMEOUT=$(jq -r '.timeout_seconds // 120' "$ZTC_CONTEXT_FILE")
CHECK_INTERVAL=$(jq -r '.check_interval // 3' "$ZTC_CONTEXT_FILE")

# Validate required fields
if [[ -z "$NAMESPACE" || "$NAMESPACE" == "null" ]]; then
    echo "ERROR: namespace is required in context" >&2
    exit 1
fi

echo "Waiting for ArgoCD repo server to be responsive..."
echo "  Namespace: $NAMESPACE"
echo "  Timeout: ${TIMEOUT}s"
echo ""

ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    echo "=== Checking repo server connectivity (${ELAPSED}s / ${TIMEOUT}s) ==="
    
    # Check if repo server deployment exists
    if ! kubectl get deployment argocd-repo-server -n "$NAMESPACE" >/dev/null 2>&1; then
        echo "⏳ ArgoCD repo server deployment not found"
        sleep $CHECK_INTERVAL
        ELAPSED=$((ELAPSED + CHECK_INTERVAL))
        continue
    fi
    
    # Check if repo server pod is ready
    REPO_POD_READY=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=argocd-repo-server -o json 2>/dev/null | jq '[.items[] | select(.status.conditions[] | select(.type=="Ready" and .status=="True"))] | length' 2>/dev/null || echo "0")
    
    if [[ "$REPO_POD_READY" -eq 0 ]]; then
        echo "⏳ ArgoCD repo server pod not ready yet"
        sleep $CHECK_INTERVAL
        ELAPSED=$((ELAPSED + CHECK_INTERVAL))
        continue
    fi
    
    # Test repo server connectivity (port 8081)
    echo "Testing repo server connectivity on port 8081..."
    if kubectl exec -n "$NAMESPACE" deployment/argocd-repo-server -- sh -c "timeout 5 bash -c '</dev/tcp/localhost/8081'" 2>/dev/null; then
        echo "✓ Repo server is responsive on port 8081"
        
        # Test repo server health endpoint (port 8084)
        echo "Testing repo server health endpoint on port 8084..."
        if kubectl exec -n "$NAMESPACE" deployment/argocd-repo-server -- sh -c "timeout 5 bash -c '</dev/tcp/localhost/8084'" 2>/dev/null; then
            echo "✓ Repo server health endpoint is responsive"
        else
            echo "⚠️  Repo server health endpoint not responsive (but continuing)"
        fi
        
        # Final validation - try to test ArgoCD API functionality
        echo "Validating ArgoCD functionality..."
        if kubectl get applications -n "$NAMESPACE" >/dev/null 2>&1; then
            echo "✓ ArgoCD API is functional"
        else
            echo "⚠️  ArgoCD API not fully functional yet (but repo server is ready)"
        fi
        
        echo ""
        echo "✓ ArgoCD repo server is ready and responsive!"
        echo ""
        exit 0
    else
        echo "⏳ Repo server not responsive on port 8081"
    fi
    
    echo ""
    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED + CHECK_INTERVAL))
done

# Timeout reached
echo ""
echo "ERROR: Timeout waiting for ArgoCD repo server to be responsive" >&2
echo ""

echo "Troubleshooting information:" >&2
echo ""

# Show repo server pod status
echo "Repo Server Pod Status:" >&2
kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=argocd-repo-server 2>/dev/null || echo "Failed to get repo server pods" >&2

echo ""
echo "Repo Server Service Status:" >&2
kubectl get svc -n "$NAMESPACE" argocd-repo-server 2>/dev/null || echo "Failed to get repo server service" >&2

echo ""
echo "Troubleshooting commands:" >&2
echo "  kubectl logs -n $NAMESPACE deployment/argocd-repo-server" >&2
echo "  kubectl describe pod -n $NAMESPACE -l app.kubernetes.io/name=argocd-repo-server" >&2
echo "  kubectl port-forward -n $NAMESPACE svc/argocd-repo-server 8081:8081" >&2
echo ""

exit 1
