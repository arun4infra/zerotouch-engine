#!/usr/bin/env bash
# Source: (new) - Wait for external-dns deployment
# Migration: New script following established wait pattern
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Validate context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo -e "${RED}ERROR: ZTC_CONTEXT_FILE not set${NC}" >&2
    exit 1
fi

if [[ ! -f "$ZTC_CONTEXT_FILE" ]]; then
    echo -e "${RED}ERROR: Context file not found: $ZTC_CONTEXT_FILE${NC}" >&2
    exit 1
fi

# Parse context with jq
NAMESPACE=$(jq -r '.namespace' "$ZTC_CONTEXT_FILE")
TIMEOUT=$(jq -r '.timeout_seconds // 300' "$ZTC_CONTEXT_FILE")
CHECK_INTERVAL=$(jq -r '.check_interval // 5' "$ZTC_CONTEXT_FILE")

# Validate required fields
if [[ -z "$NAMESPACE" || "$NAMESPACE" == "null" ]]; then
    echo -e "${RED}ERROR: namespace is required in context${NC}" >&2
    exit 1
fi

echo -e "${GREEN}Waiting for External-DNS deployment in namespace: $NAMESPACE${NC}"
echo -e "${GREEN}Timeout: ${TIMEOUT}s, Check interval: ${CHECK_INTERVAL}s${NC}"

# Kubectl retry function
kubectl_retry() {
    local max_attempts=5
    local attempt=1
    while [ $attempt -le $max_attempts ]; do
        if kubectl "$@" 2>/dev/null; then
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done
    return 1
}

# Check External-DNS deployment
check_external_dns() {
    if ! kubectl_retry get deployment external-dns -n "$NAMESPACE" >/dev/null 2>&1; then
        echo -e "${RED}✗ Deployment external-dns not found${NC}"
        return 1
    fi
    
    local ready=$(kubectl_retry get deployment external-dns -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    local total=$(kubectl_retry get deployment external-dns -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    
    if [ "$ready" -eq "$total" ] && [ "$total" -gt 0 ]; then
        echo -e "${GREEN}✓ external-dns: $ready/$total ready${NC}"
        return 0
    else
        echo -e "${YELLOW}⏳ external-dns: $ready/$total ready${NC}"
        return 1
    fi
}

# Wait loop
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    echo -e "${YELLOW}Checking External-DNS ($((ELAPSED))s elapsed)...${NC}"
    
    if check_external_dns; then
        echo ""
        echo -e "${GREEN}✓ External-DNS deployment is ready!${NC}"
        exit 0
    fi
    
    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED + CHECK_INTERVAL))
done

# Timeout reached
echo ""
echo -e "${RED}ERROR: Timeout after ${TIMEOUT}s${NC}" >&2
echo -e "${YELLOW}Troubleshooting commands:${NC}"
echo "  kubectl get deployment -n $NAMESPACE"
echo "  kubectl get pods -n $NAMESPACE"
echo "  kubectl describe deployment external-dns -n $NAMESPACE"
exit 1
