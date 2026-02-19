#!/usr/bin/env bash
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

# Validate required fields
if [[ -z "$NAMESPACE" || "$NAMESPACE" == "null" ]]; then
    echo -e "${RED}ERROR: namespace is required in context${NC}" >&2
    exit 1
fi

echo -e "${GREEN}Validating cert-manager in namespace: $NAMESPACE${NC}"

# Check deployments are available
DEPLOYMENTS=("cert-manager" "cert-manager-webhook" "cert-manager-cainjector")
ALL_HEALTHY=true

for deployment in "${DEPLOYMENTS[@]}"; do
    if ! kubectl get deployment "$deployment" -n "$NAMESPACE" >/dev/null 2>&1; then
        echo -e "${RED}✗ Deployment $deployment not found${NC}"
        ALL_HEALTHY=false
        continue
    fi
    
    AVAILABLE=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' 2>/dev/null || echo "False")
    
    if [ "$AVAILABLE" = "True" ]; then
        echo -e "${GREEN}✓ $deployment is available${NC}"
    else
        echo -e "${RED}✗ $deployment is not available${NC}"
        ALL_HEALTHY=false
    fi
done

# Check all pods are running and ready
PODS=$(kubectl get pods -n "$NAMESPACE" -o json 2>/dev/null || echo '{"items":[]}')
TOTAL_PODS=$(echo "$PODS" | jq -r '.items | length')
READY_PODS=0

while IFS='|' read -r name phase ready; do
    if [ -z "$name" ]; then continue; fi
    
    if [ "$phase" = "Running" ] && [ "$ready" = "true" ]; then
        READY_PODS=$((READY_PODS + 1))
        echo -e "${GREEN}✓ Pod $name is running and ready${NC}"
    else
        echo -e "${RED}✗ Pod $name: phase=$phase, ready=$ready${NC}"
        ALL_HEALTHY=false
    fi
done < <(echo "$PODS" | jq -r '.items[] | "\(.metadata.name)|\(.status.phase)|\(.status.conditions[] | select(.type=="Ready") | .status)"')

if [ "$ALL_HEALTHY" = true ]; then
    echo ""
    echo -e "${GREEN}✓ Cert-manager validation passed: all components healthy${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}✗ Cert-manager validation failed${NC}" >&2
    exit 1
fi
