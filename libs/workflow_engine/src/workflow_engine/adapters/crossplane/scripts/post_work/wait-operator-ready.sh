#!/usr/bin/env bash
set -euo pipefail

# Source: zerotouch-platform/scripts/bootstrap/wait/13-wait-service-dependencies.sh
# Migration: Extracted crossplane-system pod wait logic, converted CLI args to JSON context

# Wait for Crossplane Operator to be Ready
# Waits for crossplane deployment and all crossplane-system pods to reach Running status

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
TIMEOUT=$(jq -r '.timeout_seconds // 300' "$ZTC_CONTEXT_FILE")
CHECK_INTERVAL=$(jq -r '.check_interval // 5' "$ZTC_CONTEXT_FILE")

# Validate required fields
if [[ -z "$NAMESPACE" || "$NAMESPACE" == "null" ]]; then
    echo "ERROR: namespace is required in context" >&2
    exit 1
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Waiting for Crossplane operator to be ready..."
echo "  Namespace: $NAMESPACE"
echo "  Timeout: ${TIMEOUT}s"
echo ""

ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    echo -e "${YELLOW}⏳ Checking Crossplane operator (${ELAPSED}s / ${TIMEOUT}s)...${NC}"
    
    # Check if namespace exists
    if ! kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
        echo "⏳ Namespace '$NAMESPACE' not found"
        sleep $CHECK_INTERVAL
        ELAPSED=$((ELAPSED + CHECK_INTERVAL))
        continue
    fi
    
    # Check crossplane deployment
    if ! kubectl get deployment crossplane -n "$NAMESPACE" >/dev/null 2>&1; then
        echo "⏳ Crossplane deployment not found"
        sleep $CHECK_INTERVAL
        ELAPSED=$((ELAPSED + CHECK_INTERVAL))
        continue
    fi
    
    # Check deployment status
    READY_REPLICAS=$(kubectl get deployment crossplane -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    DESIRED_REPLICAS=$(kubectl get deployment crossplane -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    
    echo "Crossplane deployment: $READY_REPLICAS/$DESIRED_REPLICAS ready"
    
    # Check all pods in namespace
    RUNNING_PODS=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l | tr -d ' ')
    READY_PODS=$(kubectl get pods -n "$NAMESPACE" -o json 2>/dev/null | jq '[.items[] | select(.status.phase=="Running") | select(.status.conditions[]? | select(.type=="Ready" and .status=="True"))] | length' 2>/dev/null || echo "0")
    
    echo "Pods: $READY_PODS/$RUNNING_PODS ready"
    
    if [[ "$READY_REPLICAS" -eq "$DESIRED_REPLICAS" ]] && [[ "$READY_PODS" -eq "$RUNNING_PODS" ]] && [[ "$RUNNING_PODS" -gt 0 ]]; then
        echo ""
        echo -e "${GREEN}✓ Crossplane operator is ready!${NC}"
        echo ""
        
        # Show final status
        echo "Pod Status:"
        kubectl get pods -n "$NAMESPACE" -o wide
        echo ""
        exit 0
    fi
    
    # Show which pods are not ready
    if [[ "$RUNNING_PODS" -gt 0 ]]; then
        echo "Not ready pods:"
        kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | while read pod_name ready_count pod_status restarts age; do
            if [[ "$pod_status" != "Running" ]] || [[ "$ready_count" != *"/"* ]] || [[ "${ready_count%/*}" != "${ready_count#*/}" ]]; then
                echo "  - $pod_name: $pod_status (Ready: $ready_count)"
            fi
        done | head -10
    fi
    
    echo ""
    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED + CHECK_INTERVAL))
done

# Timeout reached
echo ""
echo -e "${RED}ERROR: Timeout waiting for Crossplane operator to be ready${NC}" >&2
echo ""
echo "Final pod status:" >&2
kubectl get pods -n "$NAMESPACE" 2>/dev/null || echo "Failed to get pods" >&2

echo ""
echo "Troubleshooting commands:" >&2
echo "  kubectl get deployment crossplane -n $NAMESPACE" >&2
echo "  kubectl get pods -n $NAMESPACE" >&2
echo "  kubectl describe deployment crossplane -n $NAMESPACE" >&2
echo "  kubectl logs -n $NAMESPACE -l app=crossplane" >&2
echo ""

exit 1

