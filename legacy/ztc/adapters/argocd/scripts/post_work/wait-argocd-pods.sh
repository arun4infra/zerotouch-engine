#!/usr/bin/env bash
set -euo pipefail

# Wait for ArgoCD Pods to be Ready
# Waits for all ArgoCD pods to reach Running status with ready conditions

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

echo "Waiting for ArgoCD pods to be ready..."
echo "  Namespace: $NAMESPACE"
echo "  Timeout: ${TIMEOUT}s"
echo ""

ELAPSED=0
GRACE_PERIOD=60

while [ $ELAPSED -lt $TIMEOUT ]; do
    echo "=== Checking ArgoCD pods (${ELAPSED}s / ${TIMEOUT}s) ==="
    
    # Check if namespace exists
    if ! kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
        echo "⏳ Namespace '$NAMESPACE' not found"
        sleep $CHECK_INTERVAL
        ELAPSED=$((ELAPSED + CHECK_INTERVAL))
        continue
    fi
    
    # Check if ReplicaSets are creating pods (detect stuck controllers) - only after grace period
    if [[ $ELAPSED -ge $GRACE_PERIOD ]]; then
        STUCK_RS=$(kubectl get rs -n "$NAMESPACE" -o json 2>/dev/null | jq -r '.items[] | select(.spec.replicas > 0 and .status.replicas == 0) | .metadata.name' | head -5)
        if [[ -n "$STUCK_RS" ]]; then
            echo "ERROR: ReplicaSets not creating pods after ${GRACE_PERIOD}s (controller stuck):" >&2
            echo "$STUCK_RS" | while read rs; do echo "  - $rs"; done >&2
            echo "ERROR: ArgoCD deployment failed - ReplicaSet controller issue" >&2
            exit 1
        fi
    fi
    
    # Count running workload pods
    RUNNING_PODS=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l | tr -d ' ')
    
    if [[ "$RUNNING_PODS" -eq 0 ]]; then
        echo "⏳ No running ArgoCD pods found yet"
        sleep $CHECK_INTERVAL
        ELAPSED=$((ELAPSED + CHECK_INTERVAL))
        continue
    fi
    
    # Check ready pods (only Running phase)
    READY_PODS=$(kubectl get pods -n "$NAMESPACE" -o json 2>/dev/null | jq '[.items[] | select(.status.phase=="Running") | select(.status.conditions[]? | select(.type=="Ready" and .status=="True"))] | length' 2>/dev/null || echo "0")
    
    # Check Job/CronJob pods
    COMPLETED_JOBS=$(kubectl get pods -n "$NAMESPACE" -o json 2>/dev/null | jq '[.items[] | select(.metadata.ownerReferences[]?.kind=="Job" and .status.phase=="Succeeded")] | length' 2>/dev/null || echo "0")
    FAILED_JOBS=$(kubectl get pods -n "$NAMESPACE" -o json 2>/dev/null | jq '[.items[] | select(.metadata.ownerReferences[]?.kind=="Job" and (.status.phase=="Failed" or .status.phase=="Error"))] | length' 2>/dev/null || echo "0")
    
    echo "Running pods: $READY_PODS/$RUNNING_PODS ready"
    echo "Job pods: $COMPLETED_JOBS completed, $FAILED_JOBS failed"
    
    # Fail immediately if any Job failed
    if [[ "$FAILED_JOBS" -gt 0 ]]; then
        echo ""
        echo "ERROR: Job/CronJob pods failed:" >&2
        kubectl get pods -n "$NAMESPACE" -o json 2>/dev/null | jq -r '.items[] | select(.metadata.ownerReferences[]?.kind=="Job" and (.status.phase=="Failed" or .status.phase=="Error")) | "  - \(.metadata.name) (\(.status.phase))"' >&2
        echo ""
        echo "ERROR: ArgoCD deployment failed due to job failures" >&2
        exit 1
    fi
    
    if [[ "$READY_PODS" -eq "$RUNNING_PODS" ]]; then
        echo ""
        echo "✓ All ArgoCD running pods are ready!"
        if [[ "$COMPLETED_JOBS" -gt 0 ]]; then
            echo "✓ $COMPLETED_JOBS job(s) completed successfully"
        fi
        echo ""
        
        # Show final status
        echo "Pod Status:"
        kubectl get pods -n "$NAMESPACE" -o wide
        echo ""
        exit 0
    fi
    
    # Show which pods are not ready
    echo "Not ready pods:"
    kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | while read pod_name ready_count pod_status restarts age; do
        if [[ "$pod_status" != "Completed" && "$pod_status" != "Succeeded" ]]; then
            if [[ "$pod_status" != "Running" ]] || [[ "$ready_count" != *"/"* ]] || [[ "${ready_count%/*}" != "${ready_count#*/}" ]]; then
                echo "  - $pod_name: $pod_status (Ready: $ready_count)"
            fi
        fi
    done | head -10
    
    echo ""
    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED + CHECK_INTERVAL))
done

# Timeout reached
echo ""
echo "ERROR: Timeout waiting for ArgoCD pods to be ready" >&2
echo ""
echo "Final pod status:" >&2
kubectl get pods -n "$NAMESPACE" 2>/dev/null || echo "Failed to get pods" >&2

echo ""
echo "Troubleshooting commands:" >&2
echo "  kubectl get pods -n $NAMESPACE" >&2
echo "  kubectl describe pods -n $NAMESPACE" >&2
echo "  kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=argocd-server" >&2
echo ""

exit 1
