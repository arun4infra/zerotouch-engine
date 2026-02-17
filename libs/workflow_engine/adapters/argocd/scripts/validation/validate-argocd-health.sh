#!/usr/bin/env bash
set -euo pipefail

# Validate ArgoCD Health
# Checks all ArgoCD deployments and pods are healthy

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

# Validate required fields
if [[ -z "$NAMESPACE" || "$NAMESPACE" == "null" ]]; then
    echo "ERROR: namespace is required in context" >&2
    exit 1
fi

echo "Validating ArgoCD health..."
echo "  Namespace: $NAMESPACE"
echo ""

VALIDATION_FAILED=0

# Check all ArgoCD deployments are available
echo "Checking ArgoCD deployments..."
DEPLOYMENTS=(
    "argocd-applicationset-controller"
    "argocd-dex-server"
    "argocd-notifications-controller"
    "argocd-redis"
    "argocd-repo-server"
    "argocd-server"
)

for deployment in "${DEPLOYMENTS[@]}"; do
    if ! kubectl get deployment "$deployment" -n "$NAMESPACE" &>/dev/null; then
        echo "✗ Deployment not found: $deployment" >&2
        VALIDATION_FAILED=1
        continue
    fi
    
    AVAILABLE=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo "0")
    DESIRED=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
    
    if [[ "$AVAILABLE" -eq "$DESIRED" ]]; then
        echo "✓ $deployment: $AVAILABLE/$DESIRED replicas available"
    else
        echo "✗ $deployment: $AVAILABLE/$DESIRED replicas available" >&2
        VALIDATION_FAILED=1
    fi
done

# Check ArgoCD application controller StatefulSet
echo ""
echo "Checking ArgoCD application controller..."
if ! kubectl get statefulset argocd-application-controller -n "$NAMESPACE" &>/dev/null; then
    echo "✗ StatefulSet not found: argocd-application-controller" >&2
    VALIDATION_FAILED=1
else
    READY=$(kubectl get statefulset argocd-application-controller -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    DESIRED=$(kubectl get statefulset argocd-application-controller -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
    
    if [[ "$READY" -eq "$DESIRED" ]]; then
        echo "✓ argocd-application-controller: $READY/$DESIRED replicas ready"
    else
        echo "✗ argocd-application-controller: $READY/$DESIRED replicas ready" >&2
        VALIDATION_FAILED=1
    fi
fi

# Check all pods are running and ready
echo ""
echo "Checking ArgoCD pods..."
TOTAL_PODS=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l | tr -d ' ')
READY_PODS=$(kubectl get pods -n "$NAMESPACE" -o json 2>/dev/null | jq '[.items[] | select((.status.phase=="Running" and (.status.conditions[] | select(.type=="Ready" and .status=="True"))) or .status.phase=="Succeeded")] | length' 2>/dev/null || echo "0")

if [[ "$READY_PODS" -eq "$TOTAL_PODS" ]]; then
    echo "✓ All $TOTAL_PODS ArgoCD pods are running and ready"
else
    echo "✗ Pods not ready: $READY_PODS/$TOTAL_PODS" >&2
    NOT_READY=$(kubectl get pods -n "$NAMESPACE" -o json 2>/dev/null | jq -r '.items[] | select(.status.phase!="Succeeded" and (.status.conditions[] | select(.type=="Ready" and .status!="True"))) | .metadata.name' 2>/dev/null || echo "")
    if [[ -n "$NOT_READY" ]]; then
        echo "$NOT_READY" | while read pod; do echo "  - $pod"; done >&2
    fi
    VALIDATION_FAILED=1
fi

# Use ArgoCD CLI to check component health (if available)
if command -v argocd &> /dev/null; then
    echo ""
    echo "Checking ArgoCD component health via CLI..."
    
    # Get ArgoCD server pod for port-forward
    SERVER_POD=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=argocd-server -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [[ -n "$SERVER_POD" ]]; then
        # Port-forward in background
        kubectl port-forward -n "$NAMESPACE" "$SERVER_POD" 8080:8080 &>/dev/null &
        PF_PID=$!
        trap "kill $PF_PID 2>/dev/null || true" EXIT
        
        sleep 2
        
        # Check server health
        if argocd version --server localhost:8080 --insecure &>/dev/null; then
            echo "✓ ArgoCD server is responsive"
        else
            echo "⚠️  ArgoCD server health check failed (but pods are ready)"
        fi
        
        kill $PF_PID 2>/dev/null || true
    fi
fi

echo ""
if [[ $VALIDATION_FAILED -eq 0 ]]; then
    echo "✓ ArgoCD health validation passed"
    exit 0
else
    echo "✗ ArgoCD health validation failed" >&2
    echo ""
    echo "Troubleshooting:" >&2
    echo "  kubectl get deployments -n $NAMESPACE" >&2
    echo "  kubectl get pods -n $NAMESPACE" >&2
    echo "  kubectl describe pods -n $NAMESPACE" >&2
    exit 1
fi
