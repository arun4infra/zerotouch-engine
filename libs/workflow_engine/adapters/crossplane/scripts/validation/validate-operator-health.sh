#!/usr/bin/env bash
set -euo pipefail

# Validate Crossplane Operator Health
# Checks crossplane deployment and pod health

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

echo "Validating Crossplane operator health..."
echo "  Namespace: $NAMESPACE"
echo ""

EXIT_CODE=0

# Check crossplane deployment
if ! kubectl get deployment crossplane -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "✗ Crossplane deployment not found"
    EXIT_CODE=1
else
    AVAILABLE=$(kubectl get deployment crossplane -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' 2>/dev/null || echo "False")
    
    if [[ "$AVAILABLE" == "True" ]]; then
        echo "✓ Crossplane deployment is available"
    else
        echo "✗ Crossplane deployment is not available"
        EXIT_CODE=1
    fi
fi

# Check crossplane-rbac-manager deployment
if ! kubectl get deployment crossplane-rbac-manager -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "✗ Crossplane RBAC manager deployment not found"
    EXIT_CODE=1
else
    AVAILABLE=$(kubectl get deployment crossplane-rbac-manager -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' 2>/dev/null || echo "False")
    
    if [[ "$AVAILABLE" == "True" ]]; then
        echo "✓ Crossplane RBAC manager is available"
    else
        echo "✗ Crossplane RBAC manager is not available"
        EXIT_CODE=1
    fi
fi

# Check all pods are running and ready
PODS_JSON=$(kubectl get pods -n "$NAMESPACE" -o json 2>/dev/null || echo '{"items":[]}')
TOTAL_PODS=$(echo "$PODS_JSON" | jq '.items | length')
READY_PODS=$(echo "$PODS_JSON" | jq '[.items[] | select(.status.phase=="Running") | select(.status.conditions[]? | select(.type=="Ready" and .status=="True"))] | length')

if [[ "$TOTAL_PODS" -eq 0 ]]; then
    echo "✗ No pods found in namespace $NAMESPACE"
    EXIT_CODE=1
elif [[ "$READY_PODS" -eq "$TOTAL_PODS" ]]; then
    echo "✓ All $TOTAL_PODS pods are running and ready"
else
    echo "✗ Only $READY_PODS/$TOTAL_PODS pods are ready"
    EXIT_CODE=1
    
    # Show unhealthy pods
    echo ""
    echo "Unhealthy pods:"
    kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | while read pod_name ready_count pod_status restarts age; do
        if [[ "$pod_status" != "Running" ]] || [[ "$ready_count" != *"/"* ]] || [[ "${ready_count%/*}" != "${ready_count#*/}" ]]; then
            echo "  - $pod_name: $pod_status (Ready: $ready_count)"
        fi
    done
fi

echo ""

if [[ $EXIT_CODE -eq 0 ]]; then
    echo "✓ Crossplane operator is healthy"
else
    echo "✗ Crossplane operator health check failed"
    echo ""
    echo "Check: kubectl get deployments -n $NAMESPACE"
    echo "Check: kubectl get pods -n $NAMESPACE"
fi

exit $EXIT_CODE

