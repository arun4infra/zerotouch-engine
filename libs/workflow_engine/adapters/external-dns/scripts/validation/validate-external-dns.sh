#!/usr/bin/env bash
# Validation script for External-DNS deployment
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

# Parse context
NAMESPACE=$(jq -r '.namespace' "$ZTC_CONTEXT_FILE")

# Validate required fields
if [[ -z "$NAMESPACE" || "$NAMESPACE" == "null" ]]; then
    echo -e "${RED}ERROR: namespace is required in context${NC}" >&2
    exit 1
fi

echo -e "${GREEN}Validating External-DNS deployment in namespace: $NAMESPACE${NC}"

# Check deployment
if ! kubectl get deployment external-dns -n "$NAMESPACE" &>/dev/null; then
    echo -e "${RED}✗ External-DNS deployment not found${NC}" >&2
    exit 1
fi

ready=$(kubectl get deployment external-dns -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
total=$(kubectl get deployment external-dns -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")

if [ "$ready" -ne "$total" ] || [ "$total" -eq 0 ]; then
    echo -e "${RED}✗ External-DNS deployment not ready: $ready/$total${NC}" >&2
    exit 1
fi

echo -e "${GREEN}✓ External-DNS deployment ready: $ready/$total${NC}"

# Check pods
pod_count=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=external-dns --field-selector=status.phase=Running 2>/dev/null | grep -c "Running" || echo "0")

if [ "$pod_count" -eq 0 ]; then
    echo -e "${RED}✗ No External-DNS pods running${NC}" >&2
    exit 1
fi

echo -e "${GREEN}✓ External-DNS pods running: $pod_count${NC}"

echo ""
echo -e "${GREEN}✓ External-DNS validation passed!${NC}"
exit 0
